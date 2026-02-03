from contextlib import asynccontextmanager

from app_base.config import get_vector_db_settings
from fastapi import FastAPI

from app_base.adapter.vector_store.factory import vector_store_cache
from app_base.adapter.vector_store.registry import get_provider_cls
from app_base.core.log import logger


@asynccontextmanager
async def lifespan_vector_store(app: FastAPI):
    settings = get_vector_db_settings()
    logger.info(f"Initializing vector store client of kind: {settings.KIND}")
    provider_cls = get_provider_cls(settings.KIND)
    provider = provider_cls.from_config(settings)
    if hasattr(app, "state"):
        app.state.vector_store = provider
    else:
        raise RuntimeError("FastAPI app does not have 'state' attribute.")
    logger.info("Vector store client initialized successfully.")

    yield

    # Cleanup on shutdown
    provider.close()
    # Clear the vector store cache
    vector_store_cache.clear()
