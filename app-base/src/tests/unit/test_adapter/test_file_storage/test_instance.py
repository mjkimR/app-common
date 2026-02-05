import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncIterator, Any

from app_base.adapter.file_storage.instance import (
    _file_storage_client,
    close_storage_client,
    get_storage_client,
    set_file_storage_client,
    setup_storage_client,
)
from app_base.adapter.file_storage.interface import FileStorageClient
from app_base.config import FileStorageSettings


@pytest.fixture(autouse=True)
def reset_global_file_storage_client():
    """Reset the global _file_storage_client before each test."""
    # Access the global variable directly from the module
    import app_base.adapter.file_storage.instance as file_storage_instance

    original_client = file_storage_instance._file_storage_client
    yield
    # Restore the global client after the test
    file_storage_instance._file_storage_client = original_client


class MockFileStorageClient(FileStorageClient):
    def __init__(self):
        self.closed = False

    @classmethod
    async def from_config(cls, settings: FileStorageSettings) -> "FileStorageClient":
        return cls()

    async def close(self) -> None:
        self.closed = True

    async def download_file(self, file_path: str) -> bytes:
        pass

    def download_file_stream(self, file_path: str) -> AsyncIterator[bytes]:
        pass

    async def upload_file(self, file_path: str, data: bytes) -> None:
        pass

    async def delete_file(self, file_path: str) -> None:
        pass

    async def list_files(self, prefix: str) -> list[str]:
        pass

    async def file_exists(self, file_path: str) -> bool:
        pass

    async def get_file_metadata(self, file_path: str) -> dict[str, Any]:
        pass


def test_set_file_storage_client():
    mock_client = MockFileStorageClient()
    set_file_storage_client(mock_client)
    assert get_storage_client() == mock_client


def test_set_file_storage_client_already_initialized():
    mock_client = MockFileStorageClient()
    set_file_storage_client(mock_client)
    with pytest.raises(RuntimeError, match="File storage client is already initialized."):
        set_file_storage_client(MockFileStorageClient())


def test_get_storage_client_not_initialized():
    with pytest.raises(RuntimeError, match="File storage client is not initialized. Check lifespan."):
        get_storage_client()


@pytest.mark.asyncio
async def test_setup_storage_client_initializes_client():
    mock_settings = FileStorageSettings(provider="local")
    with patch(
        "app_base.adapter.file_storage.instance.FileStorageFactory.create_client",
        new_callable=AsyncMock,
    ) as mock_create_client:
        mock_create_client.return_value = MockFileStorageClient()
        await setup_storage_client(mock_settings)
        mock_create_client.assert_called_once_with(config=mock_settings)
        assert get_storage_client() == mock_create_client.return_value


@pytest.mark.asyncio
async def test_setup_storage_client_already_initialized():
    mock_client = MockFileStorageClient()
    set_file_storage_client(mock_client)
    mock_settings = FileStorageSettings(provider="local")
    with patch(
        "app_base.adapter.file_storage.instance.FileStorageFactory.create_client",
        new_callable=AsyncMock,
    ) as mock_create_client:
        await setup_storage_client(mock_settings)
        mock_create_client.assert_not_called()  # Should not be called if already initialized
        assert get_storage_client() == mock_client


@pytest.mark.asyncio
async def test_close_storage_client():
    mock_client = MockFileStorageClient()
    set_file_storage_client(mock_client)
    await close_storage_client()
    assert mock_client.closed is True
    with pytest.raises(RuntimeError, match="File storage client is not initialized. Check lifespan."):
        get_storage_client()


@pytest.mark.asyncio
async def test_close_storage_client_not_initialized():
    # Should not raise an error if client is not initialized
    await close_storage_client()
    with pytest.raises(RuntimeError, match="File storage client is not initialized. Check lifespan."):
        get_storage_client()
