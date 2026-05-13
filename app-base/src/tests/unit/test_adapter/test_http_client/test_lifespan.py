from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app_base.adapter.http_client.lifespan import lifespan_http_client
from fastapi import FastAPI


@pytest.mark.asyncio
async def test_lifespan_http_client():
    mock_app = FastAPI()

    with (
        patch(
            "app_base.adapter.http_client.lifespan.setup_http_client", new_callable=AsyncMock
        ) as mock_setup_http_client,
        patch(
            "app_base.adapter.http_client.lifespan.setup_http_sync_client", new_callable=MagicMock
        ) as mock_setup_http_sync_client,
        patch(
            "app_base.adapter.http_client.lifespan.close_http_client", new_callable=AsyncMock
        ) as mock_close_http_client,
        patch(
            "app_base.adapter.http_client.lifespan.close_http_sync_client", new_callable=MagicMock
        ) as mock_close_http_sync_client,
    ):
        async with lifespan_http_client(mock_app):
            mock_setup_http_client.assert_awaited_once()
            mock_setup_http_sync_client.assert_called_once()

            mock_close_http_client.assert_not_called()
            mock_close_http_sync_client.assert_not_called()

        mock_close_http_client.assert_awaited_once()
        mock_close_http_sync_client.assert_called_once()
