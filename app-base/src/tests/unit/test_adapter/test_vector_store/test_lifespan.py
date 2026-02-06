from unittest.mock import AsyncMock, patch

import pytest
from app_base.adapter.vector_store.lifespan import lifespan_vector_store
from fastapi import FastAPI


@pytest.mark.asyncio
async def test_lifespan_vector_store_initializes_and_cleans_up():
    mock_app = FastAPI()
    with (
        patch(
            "app_base.adapter.vector_store.lifespan.setup_vector_store_provider", new_callable=AsyncMock
        ) as mock_setup_vector_store_provider,
        patch(
            "app_base.adapter.vector_store.lifespan.close_vector_store", new_callable=AsyncMock
        ) as mock_close_vector_store,
        patch("app_base.adapter.vector_store.lifespan.vector_store_cache") as mock_vector_store_cache,
    ):
        # Create a mutable state to control the boolean value of the mock cache
        is_empty = [False]  # Initially not empty

        def mock_clear_side_effect():
            is_empty[0] = True  # Set to empty after clear is called

        mock_vector_store_cache.clear.side_effect = mock_clear_side_effect
        mock_vector_store_cache.__bool__.side_effect = lambda: not is_empty[0]

        async with lifespan_vector_store(mock_app):
            mock_setup_vector_store_provider.assert_called_once()
            mock_close_vector_store.assert_not_called()  # Should not be called until exit
            mock_vector_store_cache.clear.assert_not_called()  # Should not be called until exit

        mock_close_vector_store.assert_called_once()  # Should be called after exit
        mock_vector_store_cache.clear.assert_called_once()  # Should be called after exit
        assert not mock_vector_store_cache  # Verify cache is cleared
