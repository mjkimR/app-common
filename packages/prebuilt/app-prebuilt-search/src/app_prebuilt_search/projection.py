"""Staged reconciliation for caller-owned snapshots and vector payload schemas."""

import json
import math
import tempfile
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, nullcontext
from dataclasses import dataclass
from typing import Any, Protocol

from app_vector_store import PayloadUpdate, QdrantVectorStore, VectorPoint
from app_vector_store.store import PayloadIndex
from qdrant_client import models

from app_prebuilt_search.errors import SearchInputError, SearchSourceError
from app_prebuilt_search.schemas import SyncResult


class DocumentEmbedder(Protocol):
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class ProjectionItem:
    id: str
    text: str
    payload: dict[str, Any]


async def sync_snapshot(
    store: QdrantVectorStore,
    embedder: DocumentEmbedder,
    items: Sequence[ProjectionItem],
    existing: Mapping[str, dict[str, Any]],
    *,
    fingerprint_key: str = "fingerprint",
    batch_size: int = 64,
    indexes: Mapping[str, PayloadIndex] | None = None,
    publication: Callable[[], AbstractAsyncContextManager[Any]] | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> SyncResult:
    """Compute/spool all vectors, then validate the source inside publication scope.

    The caller owns namespace filtering and the index lock from inventory capture
    through completion. The optional publication scope revalidates the snapshot
    and fences source writers; it runs in the caller task, after model I/O. No
    vector mutation occurs if inference or scope entry fails. Publication failure
    may leave partial vector changes; the next sync repairs them. No source data
    or success markers are persisted by this primitive.
    """
    if batch_size < 1:
        raise SearchInputError("batch_size must be positive")
    # Detach caller-owned mutable payloads before any inference can yield control.
    desired = {
        item.id: ProjectionItem(item.id, item.text, json.loads(json.dumps(item.payload, allow_nan=False)))
        for item in items
    }
    if len(desired) != len(items):
        raise SearchSourceError("Duplicate projection identity")
    if any(not isinstance(item.payload.get(fingerprint_key), str) for item in desired.values()):
        raise SearchSourceError("Projection items require a string fingerprint")
    changed = [
        item
        for key, item in desired.items()
        if existing.get(key, {}).get(fingerprint_key) != item.payload[fingerprint_key]
    ]
    result = SyncResult(scanned=len(items))
    if progress:
        progress(0, len(changed))
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as staged:
        for start in range(0, len(changed), batch_size):
            batch = changed[start : start + batch_size]
            vectors = await embedder.embed_documents([item.text for item in batch])
            if len(vectors) != len(batch):
                raise SearchSourceError("Embedding provider returned an incorrect vector count")
            if any(len(v) != store.dimension or not all(math.isfinite(n) for n in v) for v in vectors):
                raise SearchSourceError("Embedding provider returned an invalid vector")
            json.dump([(item.id, vector) for item, vector in zip(batch, vectors, strict=True)], staged, allow_nan=False)
            staged.write("\n")
            result.embedded += len(batch)
            if progress:
                progress(result.embedded, len(changed))
        staged.seek(0)
        async with publication() if publication else nullcontext():
            if indexes is not None:
                await store.ensure_payload_indexes(dict(indexes))
            for line in staged:
                await store.upsert(
                    [VectorPoint(key, vector, desired[key].payload) for key, vector in json.loads(line)],
                    batch_size=batch_size,
                )
            refreshed = []
            for key, item in desired.items():
                previous = existing.get(key)
                if previous and previous.get(fingerprint_key) == item.payload[fingerprint_key]:
                    if previous != item.payload:
                        refreshed.append(PayloadUpdate(key, item.payload))
                        if len(refreshed) == batch_size:
                            result.refreshed += await store.overwrite_payloads(refreshed, batch_size=batch_size)
                            refreshed.clear()
                    else:
                        result.skipped += 1
            if refreshed:
                result.refreshed += await store.overwrite_payloads(refreshed, batch_size=batch_size)
            stale = sorted(set(existing) - set(desired))
            for start in range(0, len(stale), batch_size):
                await store.delete(models.PointIdsList(points=[key for key in stale[start : start + batch_size]]))
            result.deleted = len(stale)
    return result
