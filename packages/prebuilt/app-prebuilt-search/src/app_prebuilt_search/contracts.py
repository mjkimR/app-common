from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app_prebuilt_search.filters import FilterValue
from app_prebuilt_search.schemas import SearchHit, SearchItem, SyncResult, SyncState


class EmbeddingProvider(Protocol):
    @property
    def embedding_id(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    async def embed_query(self, text: str) -> list[float]: ...


class SearchSource(Protocol):
    def iter_items(self, session: AsyncSession, scope: str) -> AsyncIterator[SearchItem]:
        """Yield a complete scope snapshot. Raise on partial/unavailable enumeration."""
        ...

    async def hydrate(
        self, session: AsyncSession, scope: str, hits: Sequence[SearchHit], filters: Mapping[str, FilterValue]
    ) -> Sequence[SearchItem]:
        """Load current authorized items from DB, excluding missing/inaccessible ones.

        Always enforce scope in the database query. Do not commit, rollback, or
        return items not requested. The service preserves ranking and checks filters.
        """
        ...


@dataclass(frozen=True)
class IndexKey:
    """Synchronization identity. All writers of this key must share a lock."""

    index_name: str
    scope: str
    profile_id: str


@dataclass(frozen=True)
class SearchRequest:
    """Trusted application routing plus independently enforced final filters.

    The runtime must authorize the index/source pairing and constrain source reads
    by source_scope. This is an integration contract, not a public authorization API.
    """

    index_scope: str
    source_scope: str
    query: str
    filters: Mapping[str, FilterValue]
    candidate_filters: Mapping[str, FilterValue]


class SearchSyncSession(Protocol):
    def iter_items(self) -> AsyncIterator[SearchItem]:
        """Yield a complete authorized snapshot; raise if unavailable or partial."""
        ...

    async def record_success(self, result: SyncResult) -> None:
        """Record success under the same lock, after all vector writes finish."""
        ...


class SearchRuntime(Protocol):
    def sync(self, key: IndexKey) -> AbstractAsyncContextManager[SearchSyncSession]:
        """Lock before snapshot reads and hold through external writes and completion.

        Runs in the caller task: may own or join an application transaction. All
        processes writing the same index key must coordinate; a workspace-local
        lock alone cannot serialize a shared remote index. The runtime chooses
        source-writer exclusion/snapshot consistency and rejects forbidden syncs.
        """
        ...

    async def read_state(self, key: IndexKey) -> SyncState:
        """Read synchronization state in a short scope, leaving no transaction open."""
        ...

    async def hydrate(self, request: SearchRequest, hits: Sequence[SearchHit]) -> Sequence[SearchItem]:
        """Read current authorized requested items in a short read-only scope.

        Indexed metadata belongs to the old snapshot; validate it before using
        offsets or claiming a current semantic match. Return current filters and
        optional metadata explaining stale results, or omit the hit. Never return
        unrequested identities. No vector/model work belongs in this scope.
        """
        ...
