from unittest.mock import MagicMock, patch

import pytest
from app_base.adapter.vector_store.factory import VectorStoreFactory, vector_store_cache
from app_base.adapter.vector_store.interface import VectorStoreProvider
from app_base.config import VectorDBSettings
from langchain_core.vectorstores import VectorStore


class MockVectorStore(VectorStore):
    def __init__(self, collection_name: str, model_name: str):
        self.collection_name = collection_name
        self.model_name = model_name

    def add_texts(self, texts, metadatas=None, **kwargs):
        pass

    def similarity_search(self, query: str, k: int = 4, **kwargs):
        pass

    @classmethod
    def from_texts(cls, texts, embedding, metadatas=None, **kwargs):
        pass


class MockVectorStoreProvider(VectorStoreProvider):
    def __init__(self, client: MagicMock):
        super().__init__(client)

    @classmethod
    def from_config(cls, settings: VectorDBSettings) -> "MockVectorStoreProvider":
        return cls(MagicMock())

    def close(self) -> None:
        pass

    def create_vector_store(self, collection_name: str, model_name: str) -> VectorStore:
        return MockVectorStore(collection_name, model_name)


@pytest.fixture(autouse=True)
def clear_cache():
    vector_store_cache.clear()
    yield
    vector_store_cache.clear()


@pytest.fixture
def vector_store_factory():
    provider = MockVectorStoreProvider(MagicMock())
    return VectorStoreFactory(provider)


@pytest.mark.asyncio
async def test_get_vector_store_new_instance(vector_store_factory):
    collection_name = "test_collection_new"
    model_name = "test_model_new"
    with patch("app_base.adapter.vector_store.factory.get_vector_db_settings") as mock_get_settings:
        mock_get_settings.return_value = MagicMock(provider="mock")
        store = vector_store_factory.get_vector_store(collection_name, model_name)
        assert isinstance(store, MockVectorStore)
        assert store.collection_name == collection_name
        assert store.model_name == model_name
        assert (mock_get_settings.return_value.provider, collection_name, model_name) in vector_store_cache


@pytest.mark.asyncio
async def test_get_vector_store_cached_instance(vector_store_factory):
    collection_name = "test_collection_cached"
    model_name = "test_model_cached"
    with patch("app_base.adapter.vector_store.factory.get_vector_db_settings") as mock_get_settings:
        mock_get_settings.return_value = MagicMock(provider="mock")
        # First call, should create and cache
        store1 = vector_store_factory.get_vector_store(collection_name, model_name)
        # Second call, should retrieve from cache
        store2 = vector_store_factory.get_vector_store(collection_name, model_name)
        assert store1 is store2
        assert (mock_get_settings.return_value.provider, collection_name, model_name) in vector_store_cache


@pytest.mark.asyncio
async def test_vector_store_cache_different_params(vector_store_factory):
    with patch("app_base.adapter.vector_store.factory.get_vector_db_settings") as mock_get_settings:
        mock_get_settings.return_value = MagicMock(provider="mock")
        store1 = vector_store_factory.get_vector_store("collection1", "model1")
        store2 = vector_store_factory.get_vector_store("collection2", "model1")
        store3 = vector_store_factory.get_vector_store("collection1", "model2")

        assert store1 is not store2
        assert store1 is not store3
        assert len(vector_store_cache) == 3
