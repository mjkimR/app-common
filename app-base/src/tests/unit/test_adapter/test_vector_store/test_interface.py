import pytest
from abc import ABC, abstractmethod
from typing import Any
from contextlib import contextmanager

from langchain_core.vectorstores import VectorStore

from app_base.adapter.vector_store.interface import VectorStoreProvider, import_error_handler
from app_base.config import VectorDBSettings


def test_vector_store_provider_is_abstract():
    with pytest.raises(
        TypeError,
        match="Can't instantiate abstract class VectorStoreProvider without an implementation for abstract methods 'close', 'create_vector_store', 'from_config'",
    ):
        VectorStoreProvider(None)


def test_vector_store_provider_abstract_methods():
    expected_abstract_methods = {
        "from_config",
        "close",
        "create_vector_store",
    }
    assert VectorStoreProvider.__abstractmethods__ == expected_abstract_methods


class MockVectorStore(VectorStore):
    def add_texts(self, texts, metadatas=None, **kwargs):
        pass

    def similarity_search(self, query: str, k: int = 4, **kwargs):
        pass

    @classmethod
    def from_texts(cls, texts, embedding, metadatas=None, **kwargs):
        pass


class ConcreteVectorStoreProvider(VectorStoreProvider):
    """A concrete implementation for testing purposes."""

    def __init__(self, client: Any):
        super().__init__(client)

    @classmethod
    def from_config(cls, settings: VectorDBSettings) -> "ConcreteVectorStoreProvider":
        return cls(client="mock_client")

    def close(self) -> None:
        pass

    def create_vector_store(self, collection_name: str, model_name: str) -> VectorStore:
        return MockVectorStore(collection_name, model_name)


def test_concrete_vector_store_provider_instantiation():
    client = "test_client"
    provider = ConcreteVectorStoreProvider(client)
    assert isinstance(provider, VectorStoreProvider)
    assert provider.client == client


def test_import_error_handler_no_error():
    with import_error_handler("test_kind"):
        pass  # No error should be raised


def test_import_error_handler_with_import_error():
    with pytest.raises(
        ImportError,
        match="Failed to import dependencies for vector store kind 'test_kind'. Please install the required package.",
    ):
        with import_error_handler("test_kind"):
            raise ImportError("Mock import error")
