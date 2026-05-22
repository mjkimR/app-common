from unittest.mock import MagicMock

import pytest
from app_base.adapter.vector_store.interface import VectorStoreProvider
from app_base.adapter.vector_store.registry import _VECTOR_STORE_REGISTRY, get_provider_cls, register_vector_store
from app_base.config import VectorDBSettings


class MockVectorStoreProvider1(VectorStoreProvider):
    def __init__(self, client: MagicMock):
        super().__init__(client)

    @classmethod
    def from_config(cls, settings: VectorDBSettings):
        pass

    def close(self) -> None:
        pass

    def create_vector_store(self, collection_name: str, model_name: str):
        pass


class MockVectorStoreProvider2(VectorStoreProvider):
    def __init__(self, client: MagicMock):
        super().__init__(client)

    @classmethod
    def from_config(cls, settings: VectorDBSettings):
        pass

    def close(self) -> None:
        pass

    def create_vector_store(self, collection_name: str, model_name: str):
        pass


@pytest.fixture(autouse=True)
def clear_registry():
    # Clear the registry before each test
    _VECTOR_STORE_REGISTRY.clear()
    yield
    # Clear the registry after each test
    _VECTOR_STORE_REGISTRY.clear()


def test_register_vector_store():
    @register_vector_store("test_kind_1")
    class TestProvider1(MockVectorStoreProvider1):
        pass

    assert _VECTOR_STORE_REGISTRY.get("test_kind_1") == TestProvider1


def test_get_provider_cls_existing():
    @register_vector_store("test_kind_2")
    class TestProvider2(MockVectorStoreProvider2):
        pass

    provider_cls = get_provider_cls("test_kind_2")
    assert provider_cls == TestProvider2


def test_get_provider_cls_non_existing():
    with pytest.raises(ValueError, match=r"Vector Store provider for kind 'non_existing' is not registered."):
        get_provider_cls("non_existing")


def test_register_multiple_providers():
    @register_vector_store("test_kind_3")
    class TestProvider3(MockVectorStoreProvider1):
        pass

    @register_vector_store("test_kind_4")
    class TestProvider4(MockVectorStoreProvider2):
        pass

    assert _VECTOR_STORE_REGISTRY.get("test_kind_3") == TestProvider3
    assert _VECTOR_STORE_REGISTRY.get("test_kind_4") == TestProvider4
