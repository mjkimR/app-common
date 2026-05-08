from contextlib import asynccontextmanager

from fastapi import FastAPI

from app_base.adapter.nosql_db.instance import close_nosql_db, setup_nosql_db_provider
from app_base.config.nosql_db import get_nosql_db_settings


@asynccontextmanager
async def lifespan_nosql_db(app: FastAPI):
    """Lifespan context manager to initialize and cleanup the NoSQL DB provider."""
    settings = get_nosql_db_settings()
    await setup_nosql_db_provider(settings)

    yield

    # Cleanup on shutdown
    await close_nosql_db()
