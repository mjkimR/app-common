from unittest.mock import MagicMock

import pytest
from app_base.config.file_storage import FileStorageSettings, S3FileStorageSettings


@pytest.fixture
def mock_s3_settings():
    mock_settings = MagicMock(spec=FileStorageSettings)
    mock_settings.provider = "s3"
    mock_settings.config = S3FileStorageSettings()
    return mock_settings
