from unittest.mock import MagicMock, patch

import pytest
from app_base.adapter.vector_store.providers.qdrant import QdrantProvider
from app_base.ai.models import AIModelFactory


@pytest.fixture
def mock_qdrant_client():
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = False
    mock_client.create_collection.return_value = None
    return mock_client


@pytest.fixture
def mock_ai_model_factory():
    mock_factory = MagicMock(spec=AIModelFactory)
    mock_factory.get_embedding.return_value = MagicMock()
    mock_factory.get_embedding_dimension.return_value = 1536  # Example dimension
    return mock_factory


async def test_qdrant_provider_from_config_import_error(mock_qdrant_settings):
    with patch.dict("sys.modules", {"qdrant_client": None}):
        with pytest.raises(ImportError, match="Failed to import dependencies for vector store kind 'qdrant'"):
            QdrantProvider.from_config(mock_qdrant_settings)


def test_qdrant_provider_close(mock_qdrant_client):
    provider = QdrantProvider(mock_qdrant_client)
    provider.close()
    mock_qdrant_client.close.assert_called_once()


def test_create_vector_store_import_error(mock_qdrant_client, mock_ai_model_factory):
    with (
        patch.dict("sys.modules", {"langchain_qdrant": None}),
        patch("app_base.adapter.vector_store.providers.qdrant.AIModelFactory", return_value=mock_ai_model_factory),
    ):
        provider = QdrantProvider(mock_qdrant_client)
        with pytest.raises(ImportError, match="Failed to import dependencies for vector store kind 'qdrant'"):
            provider.create_vector_store("collection", "model")
