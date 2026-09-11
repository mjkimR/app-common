from unittest.mock import MagicMock

import pytest
from app_file_storage.config import FileStorageSettings


@pytest.fixture
def mock_s3_settings():
    mock_settings = MagicMock(spec=FileStorageSettings)
    mock_settings.provider = "s3"
    return mock_settings
