from collections.abc import AsyncIterator, Mapping, Sequence
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from app_prebuilt_search.filters import FilterValue
from app_prebuilt_search.schemas import SearchHit, SearchItem


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
