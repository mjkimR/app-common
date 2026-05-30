import sys
from unittest.mock import MagicMock, patch

import pytest
from app_vector_store.config import VectorDBSettings
from app_vector_store.factory import VectorStoreFactory
from app_vector_store.instance import (
    close_vector_store,
    get_vector_store,
    get_vector_store_factory,
    get_vector_store_provider,
    set_vector_store_provider,
    setup_vector_store_provider,
)
from app_vector_store.interface import VectorStoreProvider
from langchain_core.vectorstores import VectorStore


@pytest.fixture(autouse=True)
def reset_module_global_vector_store():
    try:
        instance_module = sys.modules["app_vector_store.instance"]
        instance_module._vector_store_provider = None  # pyright: ignore[reportAttributeAccessIssue]
        yield
        instance_module._vector_store_provider = None  # pyright: ignore[reportAttributeAccessIssue]
    except KeyError:
        yield


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
        self.close_called = False
        self.create_vector_store_called_with = None

    @classmethod
    def from_config(cls, settings: VectorDBSettings) -> "MockVectorStoreProvider":
        return cls(MagicMock())

    def close(self) -> None:
        self.close_called = True

    async def create_vector_store(self, collection_name: str, model_name: str) -> VectorStore:
        self.create_vector_store_called_with = (collection_name, model_name)
        return MockVectorStore(collection_name, model_name)


def test_set_vector_store_provider():
    mock_provider = MockVectorStoreProvider(MagicMock())
    set_vector_store_provider(mock_provider)
    assert get_vector_store_provider() == mock_provider


def test_set_vector_store_provider_already_initialized():
    mock_provider = MockVectorStoreProvider(MagicMock())
    set_vector_store_provider(mock_provider)
    with pytest.raises(RuntimeError, match=r"Vector Store provider is already initialized."):
        set_vector_store_provider(mock_provider)


def test_get_vector_store_provider_not_initialized():
    with pytest.raises(RuntimeError, match=r"Vector Store provider is not initialized. Check lifespan."):
        get_vector_store_provider()


def test_get_vector_store_factory():
    mock_provider = MockVectorStoreProvider(MagicMock())
    set_vector_store_provider(mock_provider)
    factory = get_vector_store_factory()
    assert isinstance(factory, VectorStoreFactory)
    assert factory.provider == mock_provider


async def test_get_vector_store():
    mock_provider = MockVectorStoreProvider(MagicMock())
    set_vector_store_provider(mock_provider)
    collection_name = "test_collection"
    model_name = "test_model"
    store = await get_vector_store(collection_name, model_name)
    assert isinstance(store, MockVectorStore)
    assert mock_provider.create_vector_store_called_with == (collection_name, model_name)


async def test_setup_vector_store_provider(mock_qdrant_settings):
    mock_settings = mock_qdrant_settings
    with patch(
        "app_vector_store.instance.get_provider_cls", return_value=MockVectorStoreProvider
    ) as mock_get_provider_cls:
        await setup_vector_store_provider(mock_settings)
        mock_get_provider_cls.assert_called_once_with(mock_settings.provider)
        assert get_vector_store_provider() is not None


async def test_setup_vector_store_provider_already_initialized(mock_qdrant_settings):
    mock_provider = MockVectorStoreProvider(MagicMock())
    set_vector_store_provider(mock_provider)
    mock_settings = mock_qdrant_settings
    with patch("app_vector_store.registry.get_provider_cls") as mock_get_provider_cls:
        await setup_vector_store_provider(mock_settings)
        mock_get_provider_cls.assert_not_called()
        assert get_vector_store_provider() == mock_provider


async def test_close_vector_store():
    mock_provider = MockVectorStoreProvider(MagicMock())
    set_vector_store_provider(mock_provider)
    await close_vector_store()
    assert mock_provider.close_called is True
    with pytest.raises(RuntimeError, match=r"Vector Store provider is not initialized. Check lifespan."):
        get_vector_store_provider()


async def test_close_vector_store_not_initialized():
    await close_vector_store()
    with pytest.raises(RuntimeError, match=r"Vector Store provider is not initialized. Check lifespan."):
        get_vector_store_provider()
