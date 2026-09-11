"""Pytest plugin: a database session wired to app-layer-base's engine accessors.

Enable it from the top-level ``conftest.py`` of a test suite::

    pytest_plugins = ["app_layer_base.testing.db"]

Backends
--------
``--db-type sqlite`` (default) runs against an in-memory SQLite. ``--db-type postgres``
stands up a real PostgreSQL with testcontainers. The two are not interchangeable:
SQLite parses ``FOR UPDATE SKIP LOCKED`` and ignores it, and its ``StaticPool`` shares
one connection, so anything asserting on row locking or on two concurrent transactions
must run on PostgreSQL and skip elsewhere (see the ``is_postgres`` fixture).

Isolation
---------
Savepoint/rollback by default on PostgreSQL: the session joins one outer transaction
via ``join_transaction_mode="create_savepoint"``, so ``session.commit()`` only releases
a savepoint and the outer transaction is rolled back afterwards. Nothing ever reaches
disk, and no cleanup query runs.

Real commits under ``@pytest.mark.real_commit``, and always on SQLite because aiosqlite
mishandles nested SAVEPOINT/RELEASE. Then each session commits for real, every session
gets its own connection, and the tables are emptied afterwards. Mark a test ``real_commit``
when something outside the test's own session has to observe the committed rows -- a
background worker, a second connection, an outbox relay.
"""

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from loguru import logger
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app_layer_base.testing.cleanup import clean_db_after_test

_POSTGRES_ALIASES = frozenset({"postgres", "postgresql", "pg"})


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--db-type",
        action="store",
        default="sqlite",
        help="Database backend for tests: sqlite (default) or postgres",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "real_commit: let the test's code commit for real (and clean up tables afterwards) "
        "instead of rolling back a savepoint; needed when another connection must see the data",
    )


def _get_base():
    """Import Base lazily so model registration happens on the test's terms."""
    from app_layer_base.base.models.mixin import Base

    return Base


@pytest.fixture(scope="session")
def db_type(request: pytest.FixtureRequest) -> str:
    return str(request.config.getoption("--db-type"))


@pytest.fixture(scope="session")
def db_url(db_type: str) -> Iterator[str]:
    """Yield the async database URL, standing up a container when asked for PostgreSQL.

    Deliberately a sync fixture: it must not depend on the event loop.
    """
    if not db_type or db_type == "sqlite":
        yield "sqlite+aiosqlite:///:memory:"
    elif db_type in _POSTGRES_ALIASES:
        from testcontainers.postgres import PostgresContainer

        postgres_version = os.getenv("POSTGRES_VERSION", "16")
        with PostgresContainer(f"postgres:{postgres_version}") as postgres:
            sync_url = postgres.get_connection_url()  # psycopg2
            yield sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://")
    else:
        raise ValueError(f"Unsupported db_type: {db_type!r}")


@pytest.fixture(scope="session")
def async_engine(db_url: str) -> Iterator[AsyncEngine]:
    """Engine shared by the whole session; created before `setup_database` runs DDL."""
    if db_url.startswith("sqlite"):
        # StaticPool keeps one connection alive, which is the only way an in-memory
        # database survives between sessions -- and also why SQLite cannot hold two
        # transactions open at once.
        engine = create_async_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        # NullPool hands every session a fresh connection, avoiding "attached to a
        # different loop" errors and letting tests hold concurrent transactions.
        engine = create_async_engine(db_url, echo=False, poolclass=NullPool)
    yield engine


@pytest.fixture(scope="session")
def is_postgres(async_engine: AsyncEngine) -> bool:
    """Skip-guard for tests that only mean something on a real PostgreSQL."""
    return not async_engine.url.drivername.startswith("sqlite")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def setup_database(async_engine: AsyncEngine) -> AsyncIterator[None]:
    base = _get_base()
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.drop_all)


@pytest.fixture(scope="session")
def session_maker(async_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture(name="session")
async def session_fixture(
    async_engine: AsyncEngine,
    session_maker: async_sessionmaker[AsyncSession],
    setup_database: None,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> AsyncIterator[AsyncSession]:
    """Function-scoped session; also patches the engine accessors the app code calls."""
    from app_layer_base.core.database import engine as db_engine_mod

    monkeypatch.setattr(db_engine_mod, "get_async_engine", lambda: async_engine)

    is_sqlite = async_engine.url.drivername.startswith("sqlite")
    wants_real_commit = request.node.get_closest_marker("real_commit") is not None

    if is_sqlite or wants_real_commit:
        monkeypatch.setattr(db_engine_mod, "get_session_maker", lambda: session_maker)
        try:
            async with session_maker() as session:
                yield session
        finally:
            try:
                tables = reversed(_get_base().metadata.sorted_tables)
                async with async_engine.connect() as conn:
                    await clean_db_after_test(async_engine.url.drivername, tables, conn)
            except Exception as e:
                logger.error(f"Error cleaning tables after test: {e}")
                raise RuntimeError(f"Error cleaning tables after test: {e}") from e
    else:
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
            try:
                async with AsyncSession(
                    conn,
                    expire_on_commit=False,
                    join_transaction_mode="create_savepoint",
                ) as session:
                    yield session
            finally:
                try:
                    await conn.rollback()
                except Exception as e:
                    logger.error(f"Error rolling back transaction: {e}")
                    raise RuntimeError(f"Error rolling back transaction: {e}") from e
