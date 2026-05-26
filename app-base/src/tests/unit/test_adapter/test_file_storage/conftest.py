from unittest.mock import MagicMock

import pytest
from app_base.config.file_storage import FileStorageSettings, S3FileStorageSettings
from pydantic import SecretStr


@pytest.fixture
def mock_s3_settings():
    mock_settings = MagicMock(spec=FileStorageSettings)
    mock_settings.provider = "s3"
    mock_settings.config = S3FileStorageSettings(
        access_key=SecretStr("test_access_key"),
        secret_key=SecretStr("test_secret_key"),
    )
    return mock_settings
