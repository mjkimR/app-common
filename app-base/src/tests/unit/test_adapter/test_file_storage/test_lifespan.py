from unittest.mock import AsyncMock, patch

import pytest
from app_base.adapter.file_storage.lifespan import lifespan_file_storage
from app_base.config import FileStorageSettings
from fastapi import FastAPI


@pytest.mark.asyncio
async def test_lifespan_file_storage_initializes_and_cleans_up():
    mock_app = FastAPI()  # FastAPI app is not actually used, but passed for type hint
    mock_settings = FileStorageSettings(FS_PROVIDER="local", **{})

    with (
        patch(
            "app_base.adapter.file_storage.lifespan.get_file_storage_settings",
            return_value=mock_settings,
        ) as mock_get_settings,
        patch(
            "app_base.adapter.file_storage.lifespan.setup_storage_client",
            new_callable=AsyncMock,
        ) as mock_setup_client,
        patch(
            "app_base.adapter.file_storage.lifespan.close_storage_client",
            new_callable=AsyncMock,
        ) as mock_close_client,
    ):
        async with lifespan_file_storage(mock_app):
            # Assertions during startup
            mock_get_settings.assert_called_once()
            mock_setup_client.assert_called_once_with(mock_settings)
            mock_close_client.assert_not_called()  # Should not be called until exit

        # Assertions during shutdown
        mock_close_client.assert_called_once()
