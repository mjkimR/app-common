from unittest.mock import AsyncMock, patch

import pytest
from app_base.adapter.file_storage.instance import (
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


@pytest.fixture
def mock_client():
    return AsyncMock(spec=FileStorageClient)


def test_set_file_storage_client(mock_client):
    set_file_storage_client(mock_client)
    assert get_storage_client() == mock_client


def test_get_storage_client_not_initialized():
    with pytest.raises(RuntimeError, match="File storage client is not initialized. Check lifespan."):
        get_storage_client()


@pytest.mark.asyncio
async def test_setup_storage_client_initializes_client(mock_client):
    mock_settings = FileStorageSettings(FS_PROVIDER="local", **{})
    with patch(
        "app_base.adapter.file_storage.instance.FileStorageFactory.create_client",
        new_callable=AsyncMock,
    ) as mock_create_client:
        mock_create_client.return_value = mock_client
        await setup_storage_client(mock_settings)
        mock_create_client.assert_called_once_with(config=mock_settings)
        assert get_storage_client() == mock_create_client.return_value


@pytest.mark.asyncio
async def test_setup_storage_client_already_initialized(mock_client):
    set_file_storage_client(mock_client)
    mock_settings = FileStorageSettings(FS_PROVIDER="local", **{})
    with patch(
        "app_base.adapter.file_storage.instance.FileStorageFactory.create_client",
        new_callable=AsyncMock,
    ) as mock_create_client:
        await setup_storage_client(mock_settings)
        mock_create_client.assert_not_called()  # Should not be called if already initialized
        assert get_storage_client() == mock_client


@pytest.mark.asyncio
async def test_close_storage_client(mock_client):
    set_file_storage_client(mock_client)
    await close_storage_client()
    with pytest.raises(RuntimeError, match="File storage client is not initialized. Check lifespan."):
        get_storage_client()


@pytest.mark.asyncio
async def test_close_storage_client_not_initialized():
    # Should not raise an error if client is not initialized
    await close_storage_client()
    with pytest.raises(RuntimeError, match="File storage client is not initialized. Check lifespan."):
        get_storage_client()
