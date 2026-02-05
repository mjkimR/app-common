from contextlib import asynccontextmanager

from fastapi import FastAPI

from app_base.adapter.vector_store.factory import vector_store_cache
from app_base.adapter.vector_store.instance import close_vector_store, setup_vector_store_provider
from app_base.config import get_vector_db_settings


@asynccontextmanager
async def lifespan_vector_store(app: FastAPI):
    settings = get_vector_db_settings()
    await setup_vector_store_provider(settings)

    yield

    # Cleanup on shutdown
    await close_vector_store()
    # Clear the vector store cache
    vector_store_cache.clear()
