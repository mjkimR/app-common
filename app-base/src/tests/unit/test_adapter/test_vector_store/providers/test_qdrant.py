import pytest
from unittest.mock import MagicMock, patch

from app_base.adapter.vector_store.providers.qdrant import QdrantProvider
from app_base.ai.models import AIModelFactory
from app_base.config import VectorDBSettings
from app_base.config.vector_db import QdrantSettings


@pytest.fixture
def mock_qdrant_settings():
    return VectorDBSettings(
        provider="qdrant",
        config=QdrantSettings(url="http://localhost:6333", api_key="test_api_key"),
    )


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

    @pytest.mark.asyncio
    async def test_qdrant_provider_from_config(mock_qdrant_settings, mock_qdrant_client):
        with patch(
            "app_base.adapter.vector_store.providers.qdrant.QdrantProvider.from_config.<locals>.QdrantClient",
            return_value=mock_qdrant_client,
        ):
            provider = QdrantProvider.from_config(mock_qdrant_settings)
        assert isinstance(provider, QdrantProvider)
        assert provider.client == mock_qdrant_client
        mock_qdrant_client.assert_called_once_with(url="http://localhost:6333", api_key="test_api_key")

    @pytest.mark.asyncio
    async def test_qdrant_provider_from_config_no_api_key(mock_qdrant_settings, mock_qdrant_client):
        mock_qdrant_settings.config.api_key = None
        with patch(
            "app_base.adapter.vector_store.providers.qdrant.QdrantProvider.from_config.<locals>.QdrantClient",
            return_value=mock_qdrant_client,
        ):
            provider = QdrantProvider.from_config(mock_qdrant_settings)
        assert isinstance(provider, QdrantProvider)
        assert provider.client == mock_qdrant_client
        mock_qdrant_client.assert_called_once_with(url="http://localhost:6333", api_key=None)


@pytest.mark.asyncio
async def test_qdrant_provider_from_config_import_error(mock_qdrant_settings):
    with patch.dict("sys.modules", {"qdrant_client": None}):
        with pytest.raises(ImportError, match="Failed to import dependencies for vector store kind 'qdrant'"):
            QdrantProvider.from_config(mock_qdrant_settings)


def test_qdrant_provider_close(mock_qdrant_client):
    provider = QdrantProvider(mock_qdrant_client)
    provider.close()
    mock_qdrant_client.close.assert_called_once()

    def test_create_vector_store_new_collection(mock_qdrant_client, mock_ai_model_factory):
        with (
            patch("app_base.adapter.vector_store.providers.qdrant.AIModelFactory", return_value=mock_ai_model_factory),
            patch(
                "app_base.adapter.vector_store.providers.qdrant.QdrantProvider.create_vector_store.<locals>.QdrantVectorStore"
            ) as MockQdrantVectorStore,
            patch("app_base.adapter.vector_store.providers.qdrant.conf") as mock_conf,
        ):
            provider = QdrantProvider(mock_qdrant_client)
        collection_name = "new_collection"
        model_name = "embedding_model"

        store = provider.create_vector_store(collection_name, model_name)

        mock_qdrant_client.collection_exists.assert_called_once_with(collection_name=collection_name)
        mock_ai_model_factory.get_embedding.assert_called_once_with(model_name)
        mock_ai_model_factory.get_embedding_dimension.assert_called_once_with(model_name)
        mock_qdrant_client.create_collection.assert_called_once_with(
            collection_name=collection_name,
            vectors_config=mock_conf.VectorParams(size=1536, distance=mock_conf.Distance.COSINE),
        )
        MockQdrantVectorStore.assert_called_once_with(
            client=mock_qdrant_client,
            collection_name=collection_name,
            embedding=mock_ai_model_factory.get_embedding.return_value,
        )
        assert store == MockQdrantVectorStore.return_value

    def test_create_vector_store_existing_collection(mock_qdrant_client, mock_ai_model_factory):
        mock_qdrant_client.collection_exists.return_value = True  # Collection already exists
        with (
            patch("app_base.adapter.vector_store.providers.qdrant.AIModelFactory", return_value=mock_ai_model_factory),
            patch(
                "app_base.adapter.vector_store.providers.qdrant.QdrantProvider.create_vector_store.<locals>.QdrantVectorStore"
            ) as MockQdrantVectorStore,
        ):
            provider = QdrantProvider(mock_qdrant_client)
        collection_name = "existing_collection"
        model_name = "embedding_model"

        store = provider.create_vector_store(collection_name, model_name)

        mock_qdrant_client.collection_exists.assert_called_once_with(collection_name=collection_name)
        mock_qdrant_client.create_collection.assert_not_called()  # Should not create if exists
        MockQdrantVectorStore.assert_called_once_with(
            client=mock_qdrant_client,
            collection_name=collection_name,
            embedding=mock_ai_model_factory.get_embedding.return_value,
        )
        assert store == MockQdrantVectorStore.return_value


def test_create_vector_store_import_error(mock_qdrant_client, mock_ai_model_factory):
    with (
        patch.dict("sys.modules", {"langchain_qdrant": None}),
        patch("app_base.adapter.vector_store.providers.qdrant.AIModelFactory", return_value=mock_ai_model_factory),
    ):
        provider = QdrantProvider(mock_qdrant_client)
        with pytest.raises(ImportError, match="Failed to import dependencies for vector store kind 'qdrant'"):
            provider.create_vector_store("collection", "model")
