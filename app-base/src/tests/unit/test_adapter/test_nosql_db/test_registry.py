from unittest.mock import MagicMock

import pytest
from app_base.adapter.nosql_db.interface import NoSQLDBProvider
from app_base.adapter.nosql_db.registry import (
    _NOSQL_DB_REGISTRY,
    get_provider_cls,
    register_nosql_db,
)
from app_base.config.nosql_db import NoSQLDBSettings


class MockProvider1(NoSQLDBProvider):
    @classmethod
    def from_config(cls, settings: NoSQLDBSettings):
        return cls(MagicMock())

    def close(self):
        pass

    async def get_document(self, collection, document_id):
        pass

    async def create_document(self, collection, document_id, data):
        pass

    async def update_document(self, collection, document_id, data):
        pass

    async def delete_document(self, collection, document_id):
        pass

    async def list_documents(self, collection, filters=None):
        return []


class MockProvider2(NoSQLDBProvider):
    @classmethod
    def from_config(cls, settings: NoSQLDBSettings):
        return cls(MagicMock())

    def close(self):
        pass

    async def get_document(self, collection, document_id):
        pass

    async def create_document(self, collection, document_id, data):
        pass

    async def update_document(self, collection, document_id, data):
        pass

    async def delete_document(self, collection, document_id):
        pass

    async def list_documents(self, collection, filters=None):
        return []


@pytest.fixture(autouse=True)
def clear_registry():
    _NOSQL_DB_REGISTRY.clear()
    yield
    _NOSQL_DB_REGISTRY.clear()


def test_register_nosql_db():
    @register_nosql_db("test_kind_1")
    class TestProvider(MockProvider1):
        pass

    assert _NOSQL_DB_REGISTRY.get("test_kind_1") == TestProvider


def test_get_provider_cls_existing():
    @register_nosql_db("test_kind_2")
    class TestProvider(MockProvider2):
        pass

    provider_cls = get_provider_cls("test_kind_2")
    assert provider_cls == TestProvider


def test_get_provider_cls_non_existing():
    with pytest.raises(ValueError, match=r"NoSQL DB provider for kind 'non_existing' is not registered."):
        get_provider_cls("non_existing")


def test_register_multiple_providers():
    @register_nosql_db("test_kind_3")
    class TestProvider3(MockProvider1):
        pass

    @register_nosql_db("test_kind_4")
    class TestProvider4(MockProvider2):
        pass

    assert _NOSQL_DB_REGISTRY.get("test_kind_3") == TestProvider3
    assert _NOSQL_DB_REGISTRY.get("test_kind_4") == TestProvider4
