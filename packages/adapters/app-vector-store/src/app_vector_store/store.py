import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from qdrant_client import AsyncQdrantClient, models
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.local.async_qdrant_local import AsyncQdrantLocal

type PointId = int | str
type PayloadIndex = (
    models.PayloadSchemaType
    | models.KeywordIndexParams
    | models.IntegerIndexParams
    | models.FloatIndexParams
    | models.GeoIndexParams
    | models.TextIndexParams
    | models.BoolIndexParams
    | models.DatetimeIndexParams
    | models.UuidIndexParams
)


@dataclass(frozen=True)
class VectorPoint:
    """Qdrant integer/UUID ID, externally computed dense vector, and application payload."""

    id: PointId
    vector: list[float]
    payload: dict[str, Any] = field(default_factory=dict)


class CollectionMismatchError(ValueError):
    """An existing collection belongs to a different embedding space or schema."""


class QdrantVectorStore:
    """One dense embedding space over a caller-owned async client.

    embedding_id is the Qdrant vector name. Include model/revision/preprocessing
    version in it, and use the same identity for document and query embeddings.
    No text embedding, domain identifiers, global cache, or implicit tenant scope.
    """

    def __init__(
        self,
        client: AsyncQdrantClient,
        collection_name: str,
        *,
        dimension: int,
        embedding_id: str,
        distance: models.Distance = models.Distance.COSINE,
    ) -> None:
        if not collection_name.strip() or not embedding_id.strip() or dimension <= 0:
            raise ValueError("collection_name/embedding_id must be nonempty and dimension must be positive")
        self.client = client
        self.collection_name = collection_name
        self.dimension = dimension
        self.embedding_id = embedding_id
        self.distance = distance
        self._ready = False
        self._init_lock = asyncio.Lock()

    async def ensure_collection(self) -> None:
        """Create if absent, otherwise verify schema. Never recreate or relabel data.

        Checked once per store instance. Reopen stores after external schema changes.
        """
        async with self._init_lock:
            if self._ready and await self.collection_exists():
                return
            if not await self.client.collection_exists(self.collection_name):
                try:
                    await self.client.create_collection(
                        self.collection_name,
                        vectors_config={
                            self.embedding_id: models.VectorParams(size=self.dimension, distance=self.distance)
                        },
                    )
                except UnexpectedResponse as exc:
                    # Another process may have created it; validate its schema below.
                    if exc.status_code != 409:
                        raise
            await self._validate_collection()

    async def collection_exists(self) -> bool:
        return await self.client.collection_exists(self.collection_name)

    async def validate_collection(self) -> bool:
        """Validate an existing collection without creating it or repairing indexes."""
        async with self._init_lock:
            if not await self.collection_exists():
                self._ready = False
                return False
            await self._validate_collection()
            return True

    async def _validate_collection(self) -> None:
        info = await self.client.get_collection(self.collection_name)
        vectors = info.config.params.vectors
        if not isinstance(vectors, dict) or set(vectors) != {self.embedding_id}:
            raise CollectionMismatchError(
                f"Collection {self.collection_name!r} has a different embedding_id; use a new collection and reindex"
            )
        params = vectors[self.embedding_id]
        if params.size != self.dimension or params.distance != self.distance:
            raise CollectionMismatchError(
                f"Collection {self.collection_name!r} has incompatible dimension/distance; reindex a new collection"
            )
        self._ready = True

    async def ensure_payload_indexes(self, indexes: Mapping[str, PayloadIndex]) -> None:
        """Declare indexes before ingestion. Local Qdrant filters without indexes.

        Existing index definitions must match; migrations are explicit caller work.
        """
        await self.ensure_collection()
        if isinstance(self.client._client, AsyncQdrantLocal):
            return
        schema = (await self.client.get_collection(self.collection_name)).payload_schema
        for name, requested in indexes.items():
            existing = schema.get(name)
            if existing is not None:
                matches = (
                    existing.data_type == requested
                    if isinstance(requested, models.PayloadSchemaType)
                    else existing.params == requested
                )
                if not matches:
                    raise CollectionMismatchError(f"Payload index {name!r} differs; migrate it explicitly")
                continue
            await self.client.create_payload_index(self.collection_name, name, field_schema=requested, wait=True)

    async def upsert(self, points: Sequence[VectorPoint], *, batch_size: int = 256) -> int:
        """Upsert stable IDs, replacing each point's vector and entire payload."""
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        # Validate the entire input before any writes, including earlier batches.
        for point in points:
            self._validate_vector(point.vector)
        if not points:
            return 0
        await self.ensure_collection()
        for start in range(0, len(points), batch_size):
            await self.client.upsert(
                self.collection_name,
                points=[
                    models.PointStruct(id=p.id, vector={self.embedding_id: p.vector}, payload=p.payload)
                    for p in points[start : start + batch_size]
                ],
                wait=True,
            )
        return len(points)

    async def search(
        self,
        vector: list[float],
        *,
        query_filter: models.Filter | None = None,
        limit: int = 10,
        score_threshold: float | None = None,
        offset: int = 0,
    ) -> list[models.ScoredPoint]:
        self._validate_vector(vector)
        if limit <= 0:
            raise ValueError("limit must be positive")
        if offset < 0:
            raise ValueError("offset must be nonnegative")
        if not await self.validate_collection():
            return []
        result = await self.client.query_points(
            self.collection_name,
            query=vector,
            using=self.embedding_id,
            query_filter=query_filter,
            limit=limit,
            offset=offset,
            score_threshold=score_threshold,
            with_payload=True,
            with_vectors=False,
        )
        return result.points

    async def scroll(
        self, *, query_filter: models.Filter | None = None, batch_size: int = 256
    ) -> AsyncIterator[models.Record]:
        """Iterate all matching payloads without vectors, following every page."""
        if batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if not await self.validate_collection():
            return
        offset = None
        while True:
            records, offset = await self.client.scroll(
                self.collection_name,
                scroll_filter=query_filter,
                limit=batch_size,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for record in records:
                yield record
            if offset is None:
                return

    async def delete(self, selector: models.PointIdsList | models.FilterSelector) -> None:
        """Delete by explicit IDs or filter. An empty filter deliberately matches all."""
        if not await self.validate_collection():
            return
        await self.client.delete(self.collection_name, points_selector=selector, wait=True)

    async def overwrite_payload(
        self, payload: dict[str, Any], selector: models.PointIdsList | models.FilterSelector
    ) -> None:
        """Replace payloads while preserving vectors; selector scope belongs to the app."""
        if not await self.validate_collection():
            return
        await self.client.overwrite_payload(self.collection_name, payload=payload, points=selector, wait=True)

    def _validate_vector(self, vector: list[float]) -> None:
        if len(vector) != self.dimension:
            raise ValueError(f"Expected vector dimension {self.dimension}, got {len(vector)}")
