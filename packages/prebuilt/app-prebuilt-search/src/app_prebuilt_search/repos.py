from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app_layer_base.utils.time_util import get_current_utc_time
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_prebuilt_search.errors import SearchConfigurationError
from app_prebuilt_search.models import SearchIndexState
from app_prebuilt_search.schemas import SyncResult


class SearchStateRepository:
    async def get(self, session: AsyncSession, index: str, scope: str, profile: str) -> SearchIndexState | None:
        return await session.get(SearchIndexState, (index, scope, profile))

    async def lock(self, session: AsyncSession, index: str, scope: str, profile: str) -> SearchIndexState:
        """Must be the first operation on a fresh transaction, before source reads."""
        dialect = session.get_bind().dialect.name
        if dialect == "sqlite":
            await session.execute(text("BEGIN IMMEDIATE"))
            insert = sqlite_insert
        elif dialect == "postgresql":
            insert = pg_insert
        else:
            raise SearchConfigurationError("Search synchronization supports SQLite and PostgreSQL")
        await session.execute(
            insert(SearchIndexState)
            .values(
                index_name=index,
                scope_id=scope,
                profile_id=profile,
            )
            .on_conflict_do_nothing()
        )
        stmt = (
            select(SearchIndexState)
            .where(
                SearchIndexState.index_name == index,
                SearchIndexState.scope_id == scope,
                SearchIndexState.profile_id == profile,
            )
            .with_for_update()
        )
        return (await session.execute(stmt)).scalar_one()

    def record_success(self, state: SearchIndexState, result: SyncResult) -> None:
        state.last_synced_at = get_current_utc_time()
        state.last_result = result.model_dump()


@asynccontextmanager
async def read_session(maker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """Short database-enforced read-only scope; restore SQLite connection state."""
    async with maker() as session:
        connection = await session.connection()
        dialect = connection.dialect.name
        if dialect == "sqlite":
            await connection.exec_driver_sql("BEGIN")
            await connection.exec_driver_sql("PRAGMA query_only = ON")
        elif dialect == "postgresql":
            await connection.exec_driver_sql("SET TRANSACTION READ ONLY")
        else:
            raise SearchConfigurationError("Search supports SQLite and PostgreSQL")
        try:
            yield session
        finally:
            if dialect == "sqlite":
                try:
                    await connection.exec_driver_sql("PRAGMA query_only = OFF")
                except BaseException:
                    await connection.invalidate()
                    raise
            await session.rollback()
