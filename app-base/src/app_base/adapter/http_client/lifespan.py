from contextlib import asynccontextmanager

from fastapi import FastAPI

from app_base.adapter.http_client.instance import (
    close_http_client,
    close_http_sync_client,
    setup_http_client,
    setup_http_sync_client,
)


@asynccontextmanager
async def lifespan_http_client(app: FastAPI):
    """Lifespan context manager to initialize and cleanup the HTTP clients (Async & Sync)."""
    await setup_http_client()
    setup_http_sync_client()

    yield

    # Cleanup on shutdown
    await close_http_client()
    close_http_sync_client()
