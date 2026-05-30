from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app_file_storage.config import (
    FileProviderType,
    FileStorageSettings,
)
from app_file_storage.factory import FileStorageFactory
from app_file_storage.interface import FileStorageClient


@pytest.fixture
def mock_local_settings():
    return FileStorageSettings(FS_PROVIDER=FileProviderType.LOCAL)


@pytest.fixture
def mock_s3_settings():
    return FileStorageSettings(FS_PROVIDER=FileProviderType.S3)


@pytest.fixture
def mock_none_settings():
    return FileStorageSettings(FS_PROVIDER=FileProviderType.NONE)


@pytest.fixture
def mock_unsupported_settings():
    mock_settings = MagicMock(spec=FileStorageSettings)
    mock_settings.provider = "unsupported"
    return mock_settings


async def test_create_client_local_provider(mock_local_settings):
    with patch(
        "app_file_storage.factory.FileStorageRegistry.create_client", new_callable=AsyncMock
    ) as mock_create_client:
        mock_create_client.return_value = MagicMock(spec=FileStorageClient)
        client = await FileStorageFactory.create_client(mock_local_settings)
        mock_create_client.assert_called_once_with(FileProviderType.LOCAL)
        assert client == mock_create_client.return_value


async def test_create_client_s3_provider(mock_s3_settings):
    with patch(
        "app_file_storage.factory.FileStorageRegistry.create_client", new_callable=AsyncMock
    ) as mock_create_client:
        mock_create_client.return_value = MagicMock(spec=FileStorageClient)
        client = await FileStorageFactory.create_client(mock_s3_settings)
        mock_create_client.assert_called_once_with(FileProviderType.S3)
        assert client == mock_create_client.return_value


async def test_create_client_none_provider(mock_none_settings):
    with pytest.raises(ValueError, match=r"File storage provider is set to 'none' but a client was requested."):
        await FileStorageFactory.create_client(mock_none_settings)


async def test_create_client_unsupported_provider(mock_unsupported_settings):
    # It will attempt to register defaults, then FileStorageRegistry will raise ValueError for unsupported
    with pytest.raises(ValueError, match=r"Unsupported file storage client: unsupported"):
        await FileStorageFactory.create_client(mock_unsupported_settings)
