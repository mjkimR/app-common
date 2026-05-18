"""
Database session fixtures for testing with multiple backends.
Supports SQLite (in-memory) and PostgreSQL (via testcontainers).

Strategy:
- async_engine / session_maker → session scope to reuse the connection pool.
- session → function scope; data isolation is achieved via one of two strategies:

  [Default] Savepoint/Rollback:
    Opens a single connection and begins an outer transaction.
    The session uses join_transaction_mode="create_savepoint" so that
    session.commit() only creates a savepoint internally (no real DB commit).
    After each test the outer transaction is rolled back, restoring the DB state.
    → Safe for unit tests and most integration tests.

  [opt-in] @pytest.mark.real_commit — TRUNCATE strategy:
    Allows real commits so that external components (e.g. Celery workers)
    can observe committed data during integration tests.
    → TRUNCATE is performed by _clean_db_after_integrate_test in
      integrate/conftest.py (autouse, function scope).
"""

import os

import pytest
import pytest_asyncio
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool


def get_base():
    """Lazy import of Base to avoid model registration conflicts at import time."""
    from app_base.base.models.mixin import Base

    return Base


@pytest.fixture(scope="session")
def db_url(db_type):
    """
    Spin up a testcontainer (if needed) and yield the async database URL.
    Implemented as a sync fixture so it has no dependency on the event loop.
    """
    if not db_type or db_type == "sqlite":
        yield "sqlite+aiosqlite:///:memory:"
    elif db_type in {"postgresql", "postgres", "pg"}:
        from testcontainers.postgres import PostgresContainer

        postgres_version = os.getenv("POSTGRES_VERSION", "16")
        with PostgresContainer(f"postgres:{postgres_version}") as postgres:
            sync_url = postgres.get_connection_url()  # psycopg2
            async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
            yield async_url
    else:
        raise ValueError(f"Unsupported db_type: {db_type}")


@pytest.fixture(scope="session")
def async_engine(db_url):
    """
    Async SQLAlchemy engine shared across the entire test session.
    - SQLite: StaticPool to share the same in-memory database connection.
    - PostgreSQL: NullPool to prevent "attached to a different loop" errors
      when each test function runs in its own event loop.
    Must be created before setup_database so DDL runs on the same engine/connection.
    """
    if db_url.startswith("sqlite"):
        engine = create_async_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_async_engine(db_url, echo=False, poolclass=NullPool)
    yield engine


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def setup_database(async_engine):
    """
    Create all tables before the test session and drop them afterwards.
    """
    Base = get_base()
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="session")
def session_maker(async_engine):
    """
    Async session factory shared across the entire test session.
    """
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture(name="session")
async def session_fixture(
    async_engine,
    session_maker,
    setup_database,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
):
    """
    Function-scoped async session for each test.

    - Patches get_async_engine / get_session_maker so application code uses the test engine.
    - Data isolation strategy is determined by the presence of @pytest.mark.real_commit:

      [Default] Savepoint/Rollback:
        An outer transaction is opened on a single connection.
        The session runs with join_transaction_mode="create_savepoint", meaning
        session.commit() only creates/releases a savepoint — no real commit happens.
        After the test the outer transaction is rolled back, wiping all changes.

      [@pytest.mark.real_commit] TRUNCATE:
        Real commits are allowed (e.g. so Celery workers can observe inserted data).
        Cleanup is delegated to _clean_db_after_integrate_test in integrate/conftest.py.
    """
    from app_base.core.database import engine as db_engine_mod

    monkeypatch.setattr(db_engine_mod, "get_async_engine", lambda: async_engine)

    use_real_commit = request.node.get_closest_marker("real_commit") is not None

    if use_real_commit:
        # ── TRUNCATE strategy ────────────────────────────────────────────────
        monkeypatch.setattr(db_engine_mod, "get_session_maker", lambda: session_maker)
        async with session_maker() as session:
            yield session

        from tests.utils import clean_db_after_test

        Base = get_base()
        tables = reversed(Base.metadata.sorted_tables)
        async with async_engine.connect() as conn:
            await clean_db_after_test(async_engine.url.drivername, tables, conn)
    else:
        # ── Savepoint / Rollback strategy ────────────────────────────────────
        # All DB operations happen inside one connection/transaction so that
        # rolling it back at the end undoes everything without a TRUNCATE.
        async with async_engine.connect() as conn:
            await conn.begin()
            bound_maker = async_sessionmaker(
                conn,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False,
                join_transaction_mode="create_savepoint",
            )
            monkeypatch.setattr(db_engine_mod, "get_session_maker", lambda: bound_maker)
            async with AsyncSession(
                conn,
                expire_on_commit=False,
                join_transaction_mode="create_savepoint",
            ) as session:
                yield session
            await conn.rollback()


@pytest_asyncio.fixture(name="inspect_session")
async def inspect_session_fixture(session_maker, setup_database):
    """
    Read-only inspection session for asserting database state after a test.
    Opens a separate session without committing any changes.
    """
    async with session_maker() as session:
        yield session
