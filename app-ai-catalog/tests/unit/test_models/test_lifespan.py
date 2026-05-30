from unittest.mock import MagicMock, patch

from app_ai_catalog.models.lifespan import lifespan_ai_client


async def test_lifespan_ai_client_initializes_and_cleans_up(tmp_path):
    mock_app = MagicMock()
    config_path = str(tmp_path / "catalog.yml")

    with (
        patch("app_ai_catalog.models.lifespan.setup_ai_client") as mock_setup_client,
        patch("app_ai_catalog.models.lifespan.close_ai_client") as mock_close_client,
    ):
        async with lifespan_ai_client(mock_app, config_path=config_path):
            mock_setup_client.assert_called_once_with(config_path=config_path)
            mock_close_client.assert_not_called()

        mock_close_client.assert_called_once()
