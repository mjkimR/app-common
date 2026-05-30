from unittest.mock import patch

import aiofiles
import aiofiles.os
import pytest
from app_file_storage.providers.local import LocalStorageProvider


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


async def test_from_env_creates_provider(test_root_path):
    # Ensure the root path doesn't exist before from_env is called
    if test_root_path.exists():
        await aiofiles.os.rmdir(test_root_path)

    with patch("app_file_storage.providers.local.LocalFileStorageSettings") as mock_settings_class:
        mock_settings_class.return_value.bucket_name = str(test_root_path)
        provider = await LocalStorageProvider.from_env()

    assert isinstance(provider, LocalStorageProvider)
    assert provider.root_path == test_root_path
    assert test_root_path.is_dir()  # Should create the root path


def test_get_full_path_valid(local_storage_provider, test_root_path):
    file_path = "subdir/test.txt"
    full_path = local_storage_provider._get_full_path(file_path)
    assert full_path == test_root_path / file_path


async def test_download_file_success(local_storage_provider, test_root_path):
    file_content = b"test content"
    file_path = test_root_path / "test.txt"
    file_path.write_bytes(file_content)

    downloaded_content = await local_storage_provider.download_file("test.txt")
    assert downloaded_content == file_content


async def test_download_file_not_found(local_storage_provider):
    with pytest.raises(FileNotFoundError, match=r"File not found at non_existent.txt"):
        await local_storage_provider.download_file("non_existent.txt")


async def test_download_file_stream_success(local_storage_provider, test_root_path):
    file_content = b"stream content" * 10
    file_path = test_root_path / "stream.txt"
    file_path.write_bytes(file_content)

    stream_chunks = [chunk async for chunk in local_storage_provider.download_file_stream("stream.txt")]
    downloaded_content = b"".join(stream_chunks)
    assert downloaded_content == file_content


async def test_download_file_stream_not_found(local_storage_provider):
    with pytest.raises(FileNotFoundError, match=r"File not found at non_existent_stream.txt"):
        async for _ in local_storage_provider.download_file_stream("non_existent_stream.txt"):
            pass


async def test_upload_file_success(local_storage_provider, test_root_path):
    file_content = b"upload data"
    file_name = "uploaded.txt"
    await local_storage_provider.upload_file(file_name, file_content)

    uploaded_path = test_root_path / file_name
    assert uploaded_path.read_bytes() == file_content


async def test_upload_file_creates_directories(local_storage_provider, test_root_path):
    file_content = b"nested upload"
    file_name = "nested/dir/file.txt"
    await local_storage_provider.upload_file(file_name, file_content)

    uploaded_path = test_root_path / file_name
    assert uploaded_path.read_bytes() == file_content
    assert uploaded_path.parent.is_dir()


async def test_delete_file_success(local_storage_provider, test_root_path):
    file_path = test_root_path / "to_delete.txt"
    file_path.write_bytes(b"delete me")
    assert file_path.exists()

    await local_storage_provider.delete_file("to_delete.txt")
    assert not file_path.exists()


async def test_delete_file_not_found_no_error(local_storage_provider):
    # Deleting a non-existent file should not raise an error
    await local_storage_provider.delete_file("non_existent_delete.txt")


async def test_list_files_success(local_storage_provider, test_root_path):
    (test_root_path / "a.txt").write_bytes(b"")
    (test_root_path / "subdir").mkdir(parents=True, exist_ok=True)
    (test_root_path / "subdir" / "b.txt").write_bytes(b"")
    (test_root_path / "subdir" / "c.csv").write_bytes(b"")
    (test_root_path / "another_file.log").write_bytes(b"")

    files = [file async for file in local_storage_provider.list_files("")]
    # Paths are relative to root_path, so convert back for assertion
    expected_files = ["a.txt", "another_file.log", "subdir/b.txt", "subdir/c.csv"]
    assert sorted(files) == sorted(expected_files)

    files_with_prefix = [file async for file in local_storage_provider.list_files("subdir/")]
    expected_files_with_prefix = ["subdir/b.txt", "subdir/c.csv"]
    assert sorted(files_with_prefix) == sorted(expected_files_with_prefix)


async def test_file_exists_true(local_storage_provider, test_root_path):
    file_path = test_root_path / "exists.txt"
    file_path.write_bytes(b"")
    assert await local_storage_provider.file_exists("exists.txt") is True


async def test_file_exists_false(local_storage_provider):
    assert await local_storage_provider.file_exists("does_not_exist.txt") is False


async def test_get_file_metadata_success(local_storage_provider, test_root_path):
    file_path = test_root_path / "meta.txt"
    file_content = b"metadata content"
    file_path.write_bytes(file_content)

    metadata = await local_storage_provider.get_file_metadata("meta.txt")
    assert metadata["size"] == len(file_content)
    assert "last_modified" in metadata
    assert metadata["path"] == "meta.txt"


async def test_get_file_metadata_not_found(local_storage_provider):
    with pytest.raises(FileNotFoundError, match=r"File not found at non_existent_meta.txt"):
        await local_storage_provider.get_file_metadata("non_existent_meta.txt")


async def test_close_does_nothing(local_storage_provider):
    # This method is a no-op for LocalStorageProvider, so just ensure it doesn't raise an error
    try:
        await local_storage_provider.close()
    except Exception as e:
        pytest.fail(f"close() raised an unexpected exception: {e}")
