import sys
from collections.abc import Mapping
from typing import Any
from unittest.mock import MagicMock

import pytest
from app_nosql_db.config import NoSQLDBSettings
from app_nosql_db.interface import NoSQLDBProvider


class MockNoSQLDBProvider(NoSQLDBProvider):
    """Mock NoSQL DB provider for testing."""

    def __init__(self, client: MagicMock):
        super().__init__(client)
        self.close_called = False
        self._store: dict[str, dict[str, Any]] = {}  # {collection: {doc_id: data}}

    @classmethod
    def from_config(cls, settings: NoSQLDBSettings) -> "MockNoSQLDBProvider":
        return cls(MagicMock())

    def close(self) -> None:
        self.close_called = True

    async def get_document(self, collection: str, document_id: str) -> Mapping[str, Any] | None:
        return self._store.get(collection, {}).get(document_id)

    async def create_document(self, collection: str, document_id: str, data: Mapping[str, Any]) -> None:
        self._store.setdefault(collection, {})[document_id] = dict(data)

    async def update_document(self, collection: str, document_id: str, data: Mapping[str, Any]) -> None:
        col = self._store.setdefault(collection, {})
        if document_id in col:
            col[document_id].update(data)
        else:
            col[document_id] = dict(data)

    async def delete_document(self, collection: str, document_id: str) -> None:
        self._store.get(collection, {}).pop(document_id, None)

    async def list_documents(
        self, collection: str, filters: list[tuple[str, str, Any]] | None = None
    ) -> list[Mapping[str, Any]]:
        docs = list(self._store.get(collection, {}).values())
        if not filters:
            return docs
        result = []
        for doc in docs:
            match = True
            for field, op, value in filters:
                doc_val = doc.get(field)
                if (
                    (op == "==" and doc_val != value)
                    or (op == "!=" and doc_val == value)
                    or (op == ">" and not (doc_val is not None and doc_val > value))
                    or (op == "<" and not (doc_val is not None and doc_val < value))
                ):
                    match = False
                if not match:
                    break
            if match:
                result.append(doc)
        return result


@pytest.fixture
def mock_provider():
    return MockNoSQLDBProvider(MagicMock())


@pytest.fixture(autouse=True)
def reset_nosql_db_provider():
    """Reset the global nosql db provider before/after each test."""
    instance_module = sys.modules.get("app_nosql_db.instance")
    if instance_module:
        instance_module._nosql_db_provider = None  # pyright: ignore[reportAttributeAccessIssue]
    yield
    if instance_module:
        instance_module._nosql_db_provider = None  # pyright: ignore[reportAttributeAccessIssue]
