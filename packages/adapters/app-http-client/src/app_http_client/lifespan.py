from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

from app_http_client.instance import (
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
