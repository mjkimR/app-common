import asyncio
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

import aiofiles
import aiofiles.os

from app_base.adapter.file_storage.providers.local import LocalStorageProvider
from app_base.config.file_storage import FileStorageSettings, LocalFileStorageSettings


@pytest.fixture
def test_root_path(tmp_path):
    """Provides a temporary root path for local storage tests."""
    return tmp_path / "test_local_root"


@pytest.fixture
def local_storage_provider(test_root_path):
    """Provides an initialized LocalStorageProvider instance."""
    return LocalStorageProvider(test_root_path)


def test_init_creates_root_path(tmp_path):
    new_root = tmp_path / "new_root"
    assert not new_root.exists()
    LocalStorageProvider(new_root)
    assert new_root.is_dir()


@pytest.fixture
def mock_local_settings(test_root_path):
    mock_settings = MagicMock(spec=FileStorageSettings)
    mock_settings.provider = "local"
    mock_settings.config = LocalFileStorageSettings(bucket_name=str(test_root_path))
    return mock_settings


@pytest.mark.asyncio
async def test_from_config_creates_provider(mock_local_settings, test_root_path):
    # Ensure the root path doesn't exist before from_config is called
    if test_root_path.exists():
        await aiofiles.os.rmdir(test_root_path)

    provider = await LocalStorageProvider.from_config(mock_local_settings)
    assert isinstance(provider, LocalStorageProvider)
    assert provider.root_path == test_root_path
    assert test_root_path.is_dir()  # Should create the root path


@pytest.mark.asyncio
async def test_from_config_no_config_raises_error():
    mock_settings = MagicMock(spec=FileStorageSettings)
    mock_settings.provider = "local"
    mock_settings.config = None  # Set config to None for this test case
    with pytest.raises(ValueError, match="Local storage settings are not configured."):
        await LocalStorageProvider.from_config(mock_settings)


def test_get_full_path_valid(local_storage_provider, test_root_path):
    file_path = "subdir/test.txt"
    full_path = local_storage_provider._get_full_path(file_path)
    assert full_path == test_root_path / file_path


def test_get_full_path_outside_root_raises_error(local_storage_provider, tmp_path):
    file_path = "../../evil.txt"
    with pytest.raises(ValueError, match="File path is outside the allowed storage directory."):
        local_storage_provider._get_full_path(file_path)


@pytest.mark.asyncio
async def test_download_file_success(local_storage_provider, test_root_path):
    file_content = b"test content"
    file_path = test_root_path / "test.txt"
    file_path.write_bytes(file_content)

    downloaded_content = await local_storage_provider.download_file("test.txt")
    assert downloaded_content == file_content


@pytest.mark.asyncio
async def test_download_file_not_found(local_storage_provider):
    with pytest.raises(FileNotFoundError, match="File not found at non_existent.txt"):
        await local_storage_provider.download_file("non_existent.txt")


@pytest.mark.asyncio
async def test_download_file_stream_success(local_storage_provider, test_root_path):
    file_content = b"stream content" * 10
    file_path = test_root_path / "stream.txt"
    file_path.write_bytes(file_content)

    stream_chunks = [chunk async for chunk in local_storage_provider.download_file_stream("stream.txt")]
    downloaded_content = b"".join(stream_chunks)
    assert downloaded_content == file_content


@pytest.mark.asyncio
async def test_download_file_stream_not_found(local_storage_provider):
    with pytest.raises(FileNotFoundError, match="File not found at non_existent_stream.txt"):
        async for _ in local_storage_provider.download_file_stream("non_existent_stream.txt"):
            pass


@pytest.mark.asyncio
async def test_upload_file_success(local_storage_provider, test_root_path):
    file_content = b"upload data"
    file_name = "uploaded.txt"
    await local_storage_provider.upload_file(file_name, file_content)

    uploaded_path = test_root_path / file_name
    assert uploaded_path.read_bytes() == file_content


@pytest.mark.asyncio
async def test_upload_file_creates_directories(local_storage_provider, test_root_path):
    file_content = b"nested upload"
    file_name = "nested/dir/file.txt"
    await local_storage_provider.upload_file(file_name, file_content)

    uploaded_path = test_root_path / file_name
    assert uploaded_path.read_bytes() == file_content
    assert uploaded_path.parent.is_dir()


@pytest.mark.asyncio
async def test_delete_file_success(local_storage_provider, test_root_path):
    file_path = test_root_path / "to_delete.txt"
    file_path.write_bytes(b"delete me")
    assert file_path.exists()

    await local_storage_provider.delete_file("to_delete.txt")
    assert not file_path.exists()


@pytest.mark.asyncio
async def test_delete_file_not_found_no_error(local_storage_provider):
    # Deleting a non-existent file should not raise an error
    await local_storage_provider.delete_file("non_existent_delete.txt")


@pytest.mark.asyncio
async def test_list_files_success(local_storage_provider, test_root_path):
    (test_root_path / "a.txt").write_bytes(b"")
    (test_root_path / "subdir").mkdir(parents=True, exist_ok=True)
    (test_root_path / "subdir" / "b.txt").write_bytes(b"")
    (test_root_path / "subdir" / "c.csv").write_bytes(b"")
    (test_root_path / "another_file.log").write_bytes(b"")

    files = await local_storage_provider.list_files("")
    # Paths are relative to root_path, so convert back for assertion
    expected_files = ["a.txt", "another_file.log", "subdir/b.txt", "subdir/c.csv"]
    assert sorted(files) == sorted(expected_files)

    files_with_prefix = await local_storage_provider.list_files("subdir/")
    expected_files_with_prefix = ["subdir/b.txt", "subdir/c.csv"]
    assert sorted(files_with_prefix) == sorted(expected_files_with_prefix)


@pytest.mark.asyncio
async def test_file_exists_true(local_storage_provider, test_root_path):
    file_path = test_root_path / "exists.txt"
    file_path.write_bytes(b"")
    assert await local_storage_provider.file_exists("exists.txt") is True


@pytest.mark.asyncio
async def test_file_exists_false(local_storage_provider):
    assert await local_storage_provider.file_exists("does_not_exist.txt") is False


@pytest.mark.asyncio
async def test_get_file_metadata_success(local_storage_provider, test_root_path):
    file_path = test_root_path / "meta.txt"
    file_content = b"metadata content"
    file_path.write_bytes(file_content)

    metadata = await local_storage_provider.get_file_metadata("meta.txt")
    assert metadata["size"] == len(file_content)
    assert "last_modified" in metadata
    assert metadata["path"] == "meta.txt"


@pytest.mark.asyncio
async def test_get_file_metadata_not_found(local_storage_provider):
    with pytest.raises(FileNotFoundError, match="File not found at non_existent_meta.txt"):
        await local_storage_provider.get_file_metadata("non_existent_meta.txt")


def test_close_does_nothing(local_storage_provider):
    # This method is a no-op for LocalStorageProvider, so just ensure it doesn't raise an error
    try:
        local_storage_provider.close()
    except Exception as e:
        pytest.fail(f"close() raised an unexpected exception: {e}")
