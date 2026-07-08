"""Self-contained pytest fixtures for app-prebuilt-outbox (SQLite in-memory).

Provides a function-scoped async ``session`` that also patches the app engine
accessors so code under test (e.g. ``AsyncTransaction`` inside the scheduler jobs)
uses this same test engine. SQLite uses real commits + DELETE cleanup because
aiosqlite does not reliably support nested savepoints.
"""

import logging

import pytest
import pytest_asyncio

# Import models so the Outbox table is registered on Base.metadata before create_all.
from app_prebuilt_outbox import models  # noqa: F401
from sqlalchemy import StaticPool, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _get_base():
    from app_layer_base.base.models.mixin import Base

    return Base


@pytest.fixture(scope="session")
def async_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    yield engine


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def setup_database(async_engine):
    base = _get_base()
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.drop_all)


@pytest.fixture(scope="session")
def session_maker(async_engine):
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture(name="session")
async def session_fixture(async_engine, session_maker, setup_database, monkeypatch):
    from app_layer_base.core.database import engine as db_engine_mod

    monkeypatch.setattr(db_engine_mod, "get_async_engine", lambda: async_engine)
    monkeypatch.setattr(db_engine_mod, "get_session_maker", lambda: session_maker)

    try:
        async with session_maker() as session:
            yield session
    finally:
        base = _get_base()
        async with async_engine.connect() as conn:
            await conn.execute(text("PRAGMA foreign_keys = OFF;"))
            for table in reversed(base.metadata.sorted_tables):
                await conn.execute(text(f"DELETE FROM {table.name}"))
            await conn.execute(text("PRAGMA foreign_keys = ON;"))
            await conn.commit()
