from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Document:
    """An application payload and an opaque version from one committed snapshot.

    Pass version back unchanged for the same document. Map ordering follows
    Firestore semantics; encode order-sensitive source text as a string.
    """

    key: str
    data: dict[str, Any]
    version: str


class DocumentStoreError(Exception):
    """Base for document contract errors. Operational SDK errors propagate."""


class DocumentAlreadyExists(DocumentStoreError):
    """Create-only failed because this key already exists."""


class VersionConflict(DocumentStoreError):
    """Conditional write failed because the version changed or the document vanished."""


class InvalidDocument(DocumentStoreError):
    """The stored document does not match this adapter's payload envelope."""
