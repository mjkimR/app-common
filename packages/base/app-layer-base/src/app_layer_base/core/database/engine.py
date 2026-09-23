from functools import lru_cache
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app_layer_base.config import AppSettings, get_app_settings


def engine_options(settings: AppSettings) -> dict[str, Any]:
    """Pool limits bound each process's connections; SQLite uses a pool that takes no size."""
    options: dict[str, Any] = {"pool_pre_ping": True}
    if not settings.DATABASE_URL.startswith("sqlite"):
        options.update(pool_size=settings.DB_POOL_SIZE, max_overflow=settings.DB_MAX_OVERFLOW)
    return options


@lru_cache
def get_async_engine() -> AsyncEngine:
    settings = get_app_settings()
    return create_async_engine(str(settings.DATABASE_URL), **engine_options(settings))


@lru_cache
def get_session_maker() -> async_sessionmaker[AsyncSession]:
    engine = get_async_engine()
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
