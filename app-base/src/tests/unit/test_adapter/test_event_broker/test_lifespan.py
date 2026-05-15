from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app_base.adapter.event_broker.lifespan import lifespan_event_broker
from app_base.config.event_broker import EventBrokerSettings
from fastapi import FastAPI


@pytest.mark.asyncio
async def test_lifespan_event_broker_initializes_and_cleans_up():
    mock_app = FastAPI()
    mock_settings = MagicMock(spec=EventBrokerSettings)

    with (
        patch(
            "app_base.adapter.event_broker.lifespan.get_event_broker_settings",
            return_value=mock_settings,
        ) as mock_get_settings,
        patch(
            "app_base.adapter.event_broker.lifespan.setup_event_broker",
        ) as mock_setup,
        patch(
            "app_base.adapter.event_broker.lifespan.close_event_broker",
            new_callable=AsyncMock,
        ) as mock_close,
    ):
        async with lifespan_event_broker(mock_app):
            mock_get_settings.assert_called_once()
            mock_setup.assert_called_once_with(settings=mock_settings)
            mock_close.assert_not_called()

        mock_close.assert_called_once()
