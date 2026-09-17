from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from qdrant_client import AsyncQdrantClient

from app_vector_store.config import QdrantSettings


def create_qdrant_client(settings: QdrantSettings) -> AsyncQdrantClient:
    """Create a client owned by the caller, who must await client.close()."""
    if settings.mode == "remote":
        return AsyncQdrantClient(
            url=settings.url,
            api_key=settings.api_key.get_secret_value() if settings.api_key else None,
            timeout=settings.timeout,
        )
    if settings.mode == "local":
        assert settings.path is not None
        return AsyncQdrantClient(path=str(settings.path.expanduser().resolve()))
    return AsyncQdrantClient(location=":memory:")


@asynccontextmanager
async def open_qdrant(settings: QdrantSettings) -> AsyncIterator[AsyncQdrantClient]:
    """Own one client for an application lifespan or a bounded operation."""
    client = create_qdrant_client(settings)
    try:
        yield client
    finally:
        await client.close()
