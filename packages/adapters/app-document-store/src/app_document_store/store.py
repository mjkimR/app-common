from collections.abc import Sequence
from typing import Any, Protocol

from app_document_store.types import Document


class DocumentStore(Protocol):
    """One application collection; operations never join a SQL transaction."""

    async def get(self, key: str) -> Document | None: ...

    async def get_many(self, keys: Sequence[str]) -> list[Document | None]:
        """Preserve input order and duplicates, with None for missing documents.

        Multiple batches do not promise a shared point-in-time snapshot.
        """
        ...

    async def create(self, key: str, data: dict[str, Any]) -> str:
        """Create only; return the version or raise DocumentAlreadyExists."""
        ...

    async def put(self, key: str, data: dict[str, Any], *, expected_version: str | None = None) -> str:
        """Replace the entire payload. No version means unconditional upsert.

        With a version, atomically require an existing matching document.
        """
        ...

    async def delete(self, key: str, *, expected_version: str | None = None) -> None:
        """Missing is a no-op unless a version was supplied."""
        ...
