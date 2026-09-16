"""Pytest fixtures: database session wired to app-layer-base's engine accessors."""

import os
from collections.abc import AsyncIterator, Iterator

import pytest
import pytest_asyncio
from loguru import logger
from sqlalchemy import StaticPool
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app_testing_base.db.cleanup import clean_db_after_test

_POSTGRES_ALIASES = frozenset({"postgres", "postgresql", "pg"})


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add database command-line option for pytest."""
    parser.addoption(
        "--db-type",
        action="store",
        default="sqlite",
        help="Database backend for tests: sqlite (default) or postgres",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for database and scope tests."""
    config.addinivalue_line(
        "markers",
        "real_commit: let the test's code commit for real (and clean up tables afterwards) "
        "instead of rolling back a savepoint; needed when another connection must see the data",
    )
    config.addinivalue_line(
        "markers",
        "integrate: integration tests exercising interactions between components and real database",
    )
    config.addinivalue_line(
        "markers",
        "e2e: end-to-end tests exercising the entire HTTP API stack",
    )


def _get_base():
    """Import Base lazily so model registration happens on the test's terms."""
    from app_layer_base.base.models.mixin import Base

    return Base


@pytest.fixture(scope="session")
def db_type(request: pytest.FixtureRequest) -> str:
    """Current database backend under test."""
    return str(request.config.getoption("--db-type"))


@pytest.fixture(scope="session")
def db_url(db_type: str) -> Iterator[str]:
    """Yield the async database URL, starting a Testcontainers PostgreSQL container when requested."""
    if not db_type or db_type == "sqlite":
        yield "sqlite+aiosqlite:///:memory:"
    elif db_type in _POSTGRES_ALIASES:
        from testcontainers.postgres import PostgresContainer

        postgres_version = os.getenv("POSTGRES_VERSION", "16")
        with PostgresContainer(f"postgres:{postgres_version}") as postgres:
            sync_url = postgres.get_connection_url()
            yield sync_url.replace("postgresql+psycopg2://", "postgresql+psycopg://")
    else:
        raise ValueError(f"Unsupported db_type: {db_type!r}")


@pytest.fixture(scope="session")
def async_engine(db_url: str) -> Iterator[AsyncEngine]:
    """AsyncEngine shared across the test session."""
    if db_url.startswith("sqlite"):
        engine = create_async_engine(
            db_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        engine = create_async_engine(db_url, echo=False, poolclass=NullPool)
    yield engine


@pytest.fixture(scope="session")
def is_postgres(async_engine: AsyncEngine) -> bool:
    """Guard fixture to conditionally skip tests requiring real PostgreSQL features."""
    return not async_engine.url.drivername.startswith("sqlite")


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def setup_database(async_engine: AsyncEngine) -> AsyncIterator[None]:
    """Create all schema tables before the test session and drop them when complete."""
    base = _get_base()
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)
    yield
    async with async_engine.begin() as conn:
        await conn.run_sync(base.metadata.drop_all)


@pytest.fixture(scope="session")
def session_maker(async_engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Session factory for manual session creation."""
    return async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )


@pytest_asyncio.fixture(name="session")
async def session(
    async_engine: AsyncEngine,
    session_maker: async_sessionmaker[AsyncSession],
    setup_database: None,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> AsyncIterator[AsyncSession]:
    """Function-scoped session; also patches the engine accessors that application code calls."""
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


session_fixture = session
