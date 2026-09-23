"""Async document storage independent of the SQL application stack."""

from app_document_store.client import close_firestore_client, create_firestore_client, open_firestore
from app_document_store.config import FirestoreSettings
from app_document_store.firestore import FirestoreDocumentStore
from app_document_store.store import DocumentStore
from app_document_store.types import (
    Document,
    DocumentAlreadyExists,
    DocumentStoreError,
    InvalidDocument,
    VersionConflict,
)

__all__ = [
    "Document",
    "DocumentAlreadyExists",
    "DocumentStore",
    "DocumentStoreError",
    "FirestoreDocumentStore",
    "FirestoreSettings",
    "InvalidDocument",
    "VersionConflict",
    "close_firestore_client",
    "create_firestore_client",
    "open_firestore",
]
