from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import Any, Mapping

from app_base.config.nosql_db import NoSQLDBSettings


class NoSQLDBProvider(ABC):
    def __init__(self, client: Any):
        self.client = client

    @classmethod
    @abstractmethod
    def from_config(cls, settings: NoSQLDBSettings) -> "NoSQLDBProvider":
        pass

    @abstractmethod
    def close(self) -> None:
        """Close the provider connection."""
        pass

    @abstractmethod
    async def get_document(self, collection: str, document_id: str) -> Mapping[str, Any] | None:
        """Get a single document by ID."""
        pass

    @abstractmethod
    async def create_document(self, collection: str, document_id: str, data: Mapping[str, Any]) -> None:
        """Create a new document."""
        pass

    @abstractmethod
    async def update_document(self, collection: str, document_id: str, data: Mapping[str, Any]) -> None:
        """Update an existing document."""
        pass

    @abstractmethod
    async def delete_document(self, collection: str, document_id: str) -> None:
        """Delete a document."""
        pass

    @abstractmethod
    async def list_documents(
        self, collection: str, filters: list[tuple[str, str, Any]] | None = None
    ) -> list[Mapping[str, Any]]:
        """List documents in a collection with optional filters."""
        pass


@contextmanager
def import_error_handler(kind: str):
    """Context manager to handle import errors for NoSQL database dependencies."""
    try:
        yield
    except ImportError as e:
        raise ImportError(
            f"Failed to import dependencies for NoSQL database kind '{kind}'. Please install the required package."
        ) from e
