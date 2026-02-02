from typing import TypeVar

from app_base.adapter.vector_store.interface import VectorStoreProvider

T = TypeVar("T", bound=VectorStoreProvider)

_VECTOR_STORE_REGISTRY: dict[str, type[VectorStoreProvider]] = {}


def register_vector_store(kind: str):
    def decorator(cls: type[T]) -> type[T]:
        _VECTOR_STORE_REGISTRY[kind] = cls
        return cls

    return decorator


def get_provider_cls(kind: str) -> type[VectorStoreProvider]:
    provider_cls = _VECTOR_STORE_REGISTRY.get(kind)
    if not provider_cls:
        raise ValueError(f"Vector Store provider for kind '{kind}' is not registered.")
    return provider_cls
