"""Default SQLAlchemy scopes for the reusable search engine."""

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC

from app_layer_base.core.database.transaction import AsyncTransaction
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_prebuilt_search.contracts import IndexKey, SearchRequest, SearchSource, SearchSyncSession
from app_prebuilt_search.models import SearchIndexState
from app_prebuilt_search.repos import SearchStateRepository, read_session
from app_prebuilt_search.schemas import SearchHit, SearchItem, SyncResult, SyncState


@dataclass
class _DatabaseSyncSession:
    session: AsyncSession
    source: SearchSource
    key: IndexKey
    state: SearchIndexState
    repo: SearchStateRepository

    def iter_items(self) -> AsyncIterator[SearchItem]:
        return self.source.iter_items(self.session, self.key.scope)

    async def record_success(self, result: SyncResult) -> None:
        self.repo.record_success(self.state, result)


class SQLAlchemySearchRuntime:
    """Own DB scopes; serialize syncs by index/scope/profile, not source writers.

    Do not wrap calls in a caller transaction. Applications with their own locks,
    repositories or non-DB snapshots should implement SearchRuntime instead.
    """

    def __init__(self, session_maker: async_sessionmaker[AsyncSession], source: SearchSource) -> None:
        self.session_maker = session_maker
        self.source = source
        self.repo = SearchStateRepository()

    @asynccontextmanager
    async def sync(self, key: IndexKey) -> AsyncIterator[SearchSyncSession]:
        async with AsyncTransaction(self.session_maker) as session:
            state = await self.repo.lock(session, key.index_name, key.scope, key.profile_id)
            yield _DatabaseSyncSession(session, self.source, key, state, self.repo)

    async def read_state(self, key: IndexKey) -> SyncState:
        async with read_session(self.session_maker) as session:
            state = await self.repo.get(session, key.index_name, key.scope, key.profile_id)
            last = state.last_synced_at if state else None
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            result = SyncResult.model_validate(state.last_result) if state and state.last_result else None
            return SyncState(last_synced_at=last, last_result=result)

    async def hydrate(self, request: SearchRequest, hits: Sequence[SearchHit]) -> Sequence[SearchItem]:
        async with read_session(self.session_maker) as session:
            return await self.source.hydrate(session, request.source_scope, hits, request.filters)
