from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI

from app_file_storage.config import get_file_storage_settings
from app_file_storage.instance import close_storage_client, setup_storage_client


@asynccontextmanager
async def lifespan_file_storage(app: FastAPI):
    """Lifespan context manager to initialize and cleanup the file storage client."""
    settings = get_file_storage_settings()
    await setup_storage_client(settings)

    yield

    # Cleanup on shutdown
    await close_storage_client()
