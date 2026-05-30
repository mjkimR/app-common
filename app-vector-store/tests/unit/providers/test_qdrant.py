from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app_ai_catalog.models import AIClient
from app_vector_store.providers.qdrant import QdrantProvider


@pytest.fixture
def mock_qdrant_client():
    mock_client = MagicMock()
    mock_client.collection_exists.return_value = False
    mock_client.create_collection.return_value = None
    return mock_client


@pytest.fixture
def mock_ai_model_factory():
    mock_factory = MagicMock(spec=AIClient)
    mock_factory.get_embedding.return_value = MagicMock()
    mock_factory.aget_embedding_dimension = AsyncMock(return_value=1536)
    return mock_factory


async def test_qdrant_provider_from_env_import_error():
    with (
        patch.dict("sys.modules", {"qdrant_client": None}),
        pytest.raises(ImportError, match=r"Failed to import dependencies for vector store kind 'qdrant'"),
    ):
        QdrantProvider.from_env()


def test_qdrant_provider_close(mock_qdrant_client):
    provider = QdrantProvider(mock_qdrant_client)
    provider.close()
    mock_qdrant_client.close.assert_called_once()


async def test_create_vector_store_import_error(mock_qdrant_client, mock_ai_model_factory):
    with (
        patch.dict("sys.modules", {"langchain_qdrant": None}),
        patch("app_vector_store.providers.qdrant.get_ai_client", return_value=mock_ai_model_factory),
    ):
        provider = QdrantProvider(mock_qdrant_client)
        with pytest.raises(ImportError, match=r"Failed to import dependencies for vector store kind 'qdrant'"):
            await provider.create_vector_store("collection", "model")


async def test_create_vector_store_uses_async_embedding_dimension(mock_qdrant_client, mock_ai_model_factory):
    from qdrant_client.http import models as conf

    mock_store = MagicMock()
    mock_qdrant_vector_store = MagicMock(return_value=mock_store)

    with (
        patch.dict(
            "sys.modules",
            {"langchain_qdrant": MagicMock(QdrantVectorStore=mock_qdrant_vector_store)},
        ),
        patch("app_vector_store.providers.qdrant.get_ai_client", return_value=mock_ai_model_factory),
    ):
        provider = QdrantProvider(mock_qdrant_client)
        store = await provider.create_vector_store("collection", "model")

    assert store is mock_store
    mock_ai_model_factory.get_embedding.assert_called_once_with("model")
    mock_ai_model_factory.aget_embedding_dimension.assert_awaited_once_with("model")
    mock_qdrant_client.create_collection.assert_called_once()
    _, kwargs = mock_qdrant_client.create_collection.call_args
    assert kwargs["collection_name"] == "collection"
    assert kwargs["vectors_config"] == conf.VectorParams(size=1536, distance=conf.Distance.COSINE)
