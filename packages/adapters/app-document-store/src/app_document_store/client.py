import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from google.cloud.firestore_v1 import AsyncClient

from app_document_store.config import FirestoreSettings


def create_firestore_client(settings: FirestoreSettings) -> AsyncClient:
    """Create a caller-owned client. Production uses Application Default Credentials."""
    host = os.environ.get("FIRESTORE_EMULATOR_HOST")
    if settings.mode == "emulator":
        if not host or "://" in host or "/" in host or ":" not in host:
            raise ValueError("Emulator mode requires FIRESTORE_EMULATOR_HOST=host:port (without a scheme)")
    elif host is not None:
        raise ValueError("Unset FIRESTORE_EMULATOR_HOST for firestore mode, or explicitly select emulator mode")
    return AsyncClient(project=settings.project_id, database=settings.database_id)


async def close_firestore_client(client: AsyncClient) -> None:
    """Close the async gRPC transport without instantiating an unused transport.

    In google-cloud-firestore 2.x, the inherited public close() only closes an
    HTTP transport. Keep the necessary SDK compatibility access confined here.
    """
    api = client._firestore_api_internal
    try:
        if api is not None:
            await api.transport.close()
    finally:
        client.close()


@asynccontextmanager
async def open_firestore(settings: FirestoreSettings) -> AsyncIterator[AsyncClient]:
    """Own a client within the caller's event loop, e.g. an application lifespan."""
    client = create_firestore_client(settings)
    try:
        yield client
    finally:
        await close_firestore_client(client)
