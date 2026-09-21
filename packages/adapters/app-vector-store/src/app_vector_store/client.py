import asyncio
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from functools import partial
from typing import cast

from qdrant_client import AsyncQdrantClient
from qdrant_client.local.async_qdrant_local import AsyncQdrantLocal

from app_vector_store.config import QdrantSettings
from app_vector_store.local import ThreadedLocal, drain


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
    if settings.mode == "remote":
        client = create_qdrant_client(settings)
    else:
        executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="qdrant-local")
        future = asyncio.get_running_loop().run_in_executor(executor, partial(create_qdrant_client, settings))
        try:
            client = await drain(future)
        except BaseException:
            # A cancelled constructor can still acquire a storage lock. Close it
            # on the same thread before releasing the executor.
            if not future.cancelled() and future.exception() is None:
                made = future.result()
                made._client = ThreadedLocal(cast(AsyncQdrantLocal, made._client), executor)
                await made.close()
            else:
                executor.shutdown(wait=True)
            raise
        client._client = ThreadedLocal(cast(AsyncQdrantLocal, client._client), executor)
    try:
        yield client
    finally:
        await client.close()
