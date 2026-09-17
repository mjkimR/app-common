import asyncio
import hashlib
import json
import math
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC

from app_layer_base.core.database.transaction import AsyncTransaction
from app_vector_store import QdrantVectorStore, VectorPoint
from qdrant_client import AsyncQdrantClient, models
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app_prebuilt_search.contracts import EmbeddingProvider, SearchSource
from app_prebuilt_search.errors import SearchConfigurationError, SearchInputError, SearchSourceError
from app_prebuilt_search.filters import FilterDefinition, FilterPolicy, FilterValue
from app_prebuilt_search.repos import SearchStateRepository, read_session
from app_prebuilt_search.schemas import IndexStatus, SearchHit, SearchItem, SearchResult, SearchResultItem, SyncResult


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@dataclass(frozen=True)
class SearchIndex:
    name: str
    recipe_version: str
    filters: Mapping[str, FilterDefinition] = field(default_factory=dict)
    batch_size: int = 64
    candidate_batch_size: int = 64
    candidate_budget: int = 2000

    def __post_init__(self) -> None:
        if not self.name.strip() or len(self.name) > 128 or not self.recipe_version.strip():
            raise SearchConfigurationError("Index name (1..128 characters) and recipe_version are required")
        if min(self.batch_size, self.candidate_batch_size, self.candidate_budget) <= 0:
            raise SearchConfigurationError("Batch sizes and candidate budget must be positive")


class SearchService:
    """Prebuilt orchestration with application-owned source, embeddings and connections.

    sync owns a long, serialized write transaction. search/status own short read-only
    transactions. Do not wrap these methods in a caller-owned database transaction.
    """

    def __init__(
        self,
        *,
        session_maker: async_sessionmaker[AsyncSession],
        vector_client: AsyncQdrantClient,
        embedder: EmbeddingProvider,
        source: SearchSource,
        index: SearchIndex,
    ) -> None:
        self.session_maker = session_maker
        self.embedder = embedder
        self.source = source
        self.index = index
        self.policy = FilterPolicy(index.filters)
        self.repo = SearchStateRepository()
        if not embedder.embedding_id.strip() or embedder.dimension <= 0:
            raise SearchConfigurationError("Embedding identity and positive dimension are required")
        self.profile_id = _hash(
            {
                "embedding": embedder.embedding_id,
                "dimension": embedder.dimension,
                "recipe": index.recipe_version,
                "filters": {k: v.kind for k, v in self.policy.definitions.items()},
            }
        )
        self.collection_name = f"search_{_hash(index.name)[:16]}_{self.profile_id}"
        self.store = QdrantVectorStore(
            vector_client,
            self.collection_name,
            dimension=embedder.dimension,
            embedding_id=self.profile_id,
        )

    @staticmethod
    def _scope(scope: str) -> None:
        if not scope.strip() or len(scope) > 255:
            raise SearchInputError("scope must contain 1..255 characters")

    @staticmethod
    def _point_id(scope: str, item: SearchItem) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, json.dumps([scope, item.source_id, item.item_id])))

    def _payload(self, scope: str, item: SearchItem) -> dict:
        return {
            "scope_id": scope,
            "source_id": item.source_id,
            "item_id": item.item_id,
            "fingerprint": _hash([self.profile_id, item.text]),
            "filters": item.filters,
        }

    async def status(self, *, scope: str) -> IndexStatus:
        self._scope(scope)
        exists = await self.store.validate_collection()
        async with read_session(self.session_maker) as session:
            state = await self.repo.get(session, self.index.name, scope, self.profile_id)
            last = state.last_synced_at if state else None
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            result = SyncResult.model_validate(state.last_result) if state and state.last_result else None
        return IndexStatus(
            collection_name=self.collection_name,
            profile_id=self.profile_id,
            collection_exists=exists,
            index_ready=exists and last is not None,
            last_synced_at=last,
            last_result=result,
        )

    async def sync(self, *, scope: str) -> SyncResult:
        self._scope(scope)
        # Keep the DB lock until in-flight external work finishes, even on cancellation.
        task = asyncio.create_task(self._sync(scope))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            try:
                await task
            finally:
                raise

    async def _sync(self, scope: str) -> SyncResult:
        async with AsyncTransaction(self.session_maker) as session:
            state = await self.repo.lock(session, self.index.name, scope, self.profile_id)
            items: dict[str, SearchItem] = {}
            # Enumerate fully before mutation; partial iteration must never trigger deletion.
            async for item in self.source.iter_items(session, scope):
                if not item.text.strip():
                    raise SearchSourceError("Search source yielded empty text")
                self.policy.validate_payload(item.filters)
                point_id = self._point_id(scope, item)
                if point_id in items:
                    raise SearchSourceError("Duplicate (source_id, item_id) in source snapshot")
                items[point_id] = item
            await self.store.ensure_payload_indexes(self.policy.indexes())
            existing = {
                str(record.id): record.payload or {}
                async for record in self.store.scroll(query_filter=self.policy.query(scope, {}))
                if (record.payload or {}).get("scope_id") == scope
            }
            result = SyncResult(scanned=len(items))
            changed: list[tuple[str, SearchItem, dict]] = []
            for point_id, item in items.items():
                payload = self._payload(scope, item)
                old = existing.get(point_id)
                if old is None or old.get("fingerprint") != payload["fingerprint"]:
                    changed.append((point_id, item, payload))
                elif old != payload:
                    await self.store.overwrite_payload(payload, models.PointIdsList(points=[point_id]))
                    result.refreshed += 1
                else:
                    result.skipped += 1
            for start in range(0, len(changed), self.index.batch_size):
                batch = changed[start : start + self.index.batch_size]
                vectors = await self.embedder.embed_documents([item.text for _, item, _ in batch])
                if len(vectors) != len(batch):
                    raise SearchSourceError("Embedding provider returned the wrong number of vectors")
                for vector in vectors:
                    self._validate_vector(vector)
                await self.store.upsert(
                    [
                        VectorPoint(point_id, vector, payload)
                        for (point_id, _, payload), vector in zip(batch, vectors, strict=True)
                    ],
                    batch_size=self.index.batch_size,
                )
                result.embedded += len(batch)
            stale = sorted(set(existing) - items.keys())
            for start in range(0, len(stale), self.index.batch_size):
                await self.store.delete(
                    models.PointIdsList(points=[p for p in stale[start : start + self.index.batch_size]])
                )
            result.deleted = len(stale)
            self.repo.record_success(state, result)
            return result

    def _validate_vector(self, vector: list[float]) -> None:
        if len(vector) != self.store.dimension or not all(math.isfinite(value) for value in vector):
            raise SearchSourceError("Embedding provider returned an invalid vector")

    async def search(
        self,
        *,
        scope: str,
        query: str,
        filters: Mapping[str, FilterValue] | None = None,
        limit: int = 10,
        score_threshold: float | None = None,
        group_by_source: bool = False,
    ) -> SearchResult:
        self._scope(scope)
        if not query.strip() or len(query) > 4000 or not 1 <= limit <= 100:
            raise SearchInputError("query must contain 1..4000 characters and limit must be 1..100")
        if score_threshold is not None and (not math.isfinite(score_threshold) or not -1 <= score_threshold <= 1):
            raise SearchInputError("Cosine score_threshold must be between -1 and 1")
        requested = dict(filters or {})
        query_filter = self.policy.query(scope, requested)
        status = await self.status(scope=scope)
        if not status.index_ready:
            return SearchResult(index_ready=False)
        query_vector = await self.embedder.embed_query(query)
        self._validate_vector(query_vector)
        result = SearchResult(index_ready=True)
        seen: set[tuple[str, str] | str] = set()
        offset = 0
        while offset < self.index.candidate_budget and len(result.items) < limit:
            size = min(self.index.candidate_batch_size, self.index.candidate_budget - offset)
            points = await self.store.search(
                query_vector,
                query_filter=query_filter,
                limit=size,
                offset=offset,
                score_threshold=score_threshold,
            )
            if not points:
                break
            hits = []
            for point in points:
                payload = point.payload or {}
                if payload.get("scope_id") != scope:
                    continue
                source_id, item_id = payload.get("source_id"), payload.get("item_id")
                if isinstance(source_id, str) and isinstance(item_id, str):
                    hits.append(SearchHit(source_id=source_id, item_id=item_id, score=point.score))
            async with read_session(self.session_maker) as session:
                current = await self.source.hydrate(session, scope, hits, requested)
                by_id: dict[tuple[str, str], SearchItem] = {}
                allowed = {(hit.source_id, hit.item_id) for hit in hits}
                for item in current:
                    key = (item.source_id, item.item_id)
                    if key not in allowed or key in by_id:
                        raise SearchSourceError("hydrate returned an unrequested or duplicate item")
                    self.policy.validate_payload(item.filters)
                    by_id[key] = item
                for hit in hits:
                    item = by_id.get((hit.source_id, hit.item_id))
                    if item is None or not item.text.strip() or not self.policy.matches(item.filters, requested):
                        continue
                    group = item.source_id if group_by_source else (item.source_id, item.item_id)
                    if group not in seen:
                        result.items.append(SearchResultItem(**item.model_dump(), score=hit.score))
                        seen.add(group)
                        if len(result.items) == limit:
                            break
            offset += len(points)
            if len(points) < size:
                break
        result.candidate_limit_reached = offset >= self.index.candidate_budget and len(result.items) < limit
        return result
