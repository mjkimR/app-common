from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app_base.adapter.file_storage.factory import FileStorageFactory
from app_base.adapter.file_storage.interface import FileStorageClient
from app_base.config import FileStorageSettings
from app_base.config.file_storage import LocalFileStorageSettings, NoneFileStorageSettings, S3FileStorageSettings
from pydantic import SecretStr


@pytest.fixture
def mock_local_settings():
    return FileStorageSettings(
        FS_PROVIDER="local",
        config=LocalFileStorageSettings(bucket_name="/tmp/test_local_storage"),
    )


@pytest.fixture
def mock_s3_settings():
    mock_settings = MagicMock(spec=FileStorageSettings)
    mock_settings.provider = "s3"
    mock_settings.config = S3FileStorageSettings(
        bucket_name="test_s3_bucket",
        access_key=SecretStr("test_s3_access_key"),
        secret_key=SecretStr("test_s3_secret_key"),
        region_name="us-east-1",
        endpoint_url="http://localhost:9000",
    )
    return mock_settings


@pytest.fixture
def mock_unsupported_settings():
    mock_settings = MagicMock(spec=FileStorageSettings)
    mock_settings.provider = "unsupported"
    # The config won't be used, but having a dummy one prevents AttributeError if somehow accessed.
    mock_settings.config = MagicMock(spec=NoneFileStorageSettings)
    return mock_settings


@pytest.mark.asyncio
async def test_create_client_local_provider(mock_local_settings):
    with patch(
        "app_base.adapter.file_storage.factory.LocalStorageProvider.from_config", new_callable=AsyncMock
    ) as mock_from_config:
        mock_from_config.return_value = MagicMock(spec=FileStorageClient)
        client = await FileStorageFactory.create_client(mock_local_settings)
        mock_from_config.assert_called_once_with(mock_local_settings)
        assert client == mock_from_config.return_value


@pytest.mark.asyncio
async def test_create_client_s3_provider(mock_s3_settings):
    with patch(
        "app_base.adapter.file_storage.factory.S3StorageProvider.from_config", new_callable=AsyncMock
    ) as mock_from_config:
        mock_from_config.return_value = MagicMock(spec=FileStorageClient)
        client = await FileStorageFactory.create_client(mock_s3_settings)
        mock_from_config.assert_called_once_with(mock_s3_settings)
        assert client == mock_from_config.return_value


@pytest.mark.asyncio
async def test_create_client_unsupported_provider(mock_unsupported_settings):
    with pytest.raises(ValueError, match="Unsupported file storage client: unsupported"):
        await FileStorageFactory.create_client(mock_unsupported_settings)
