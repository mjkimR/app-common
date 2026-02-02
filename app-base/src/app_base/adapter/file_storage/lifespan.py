from contextlib import asynccontextmanager

from config import get_file_storage_settings
from fastapi import FastAPI

from app_base.adapter.file_storage.factory import FileStorageFactory
from app_base.core.log import logger


@asynccontextmanager
async def lifespan_file_storage(app: FastAPI):
    settings = get_file_storage_settings()
    logger.info(f"Initializing file storage client of kind: {settings.KIND}")
    provider = await FileStorageFactory.create_client(config=settings)
    if hasattr(app, "state"):
        app.state.file_storage = provider
    else:
        raise RuntimeError("FastAPI app does not have 'state' attribute.")
    logger.info("File storage client initialized successfully.")

    yield

    # Cleanup on shutdown
    await provider.close()
