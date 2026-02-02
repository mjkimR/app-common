from typing import Annotated, Any

from fastapi import Depends, Request
from langchain_core.vectorstores import VectorStore

from app_base.adapter.vector_store.factory import VectorStoreFactory
from app_base.adapter.vector_store.interface import VectorStoreProvider


def get_vector_store_provider(request: Request) -> VectorStoreProvider:
    """
    Returns the vector store provider instance.
    The return type may vary depending on KIND.
    """
    return request.app.state.vector_store


def get_vector_store_factory(provider: Annotated[Any, Depends(get_vector_store_provider)]) -> VectorStoreFactory:
    """
    Dependency injection for FastAPI.

    Useful when collection name and embedding model name are dynamic.
    """
    return VectorStoreFactory(provider)


def get_vector_store_dependency(collection_name: str, model_name: str):
    """
    Returns a FastAPI dependency for injecting a VectorStore.

    Example:
        Depends(get_vector_store_dependency("my_collection", "openai-embedding"))
    """

    def dependency(factory: Annotated[VectorStoreFactory, Depends(get_vector_store_factory)]) -> VectorStore:
        return factory.get_vector_store(collection_name, model_name)

    return dependency
