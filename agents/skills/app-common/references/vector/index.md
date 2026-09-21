# app-vector-store

Async Qdrant storage for externally computed dense vectors. No AI catalog or LangChain dependency.

```python
from app_vector_store import QdrantSettings, QdrantVectorStore, VectorPoint, open_qdrant
from qdrant_client import models

async def example(vector: list[float], query_vector: list[float]):
    async with open_qdrant(QdrantSettings(mode="local", path="./data/vectors")) as client:
        store = QdrantVectorStore(client, "docs", dimension=384, embedding_id="model@revision:prep-v1")
        await store.ensure_payload_indexes({"project": models.PayloadSchemaType.KEYWORD})
        await store.upsert([VectorPoint(1, vector, {"project": "alpha"})])
        scope = models.Filter(must=[
            models.FieldCondition(key="project", match=models.MatchValue(value="alpha")),
        ])
        return await store.search(query_vector, query_filter=scope)
```

- Create embeddings outside this adapter; separate document and query embedding methods in the application.
- Include the model/revision/preprocessing version in `embedding_id`. It is stored as the single named vector; a mismatch in identity, dimension or distance raises `CollectionMismatchError`. Reindex into a new collection when changing embedding spaces.
- `ensure_collection()` creates or validates. Upsert/index setup may create collections; search/scroll/delete/payload replacement never do. `validate_collection()` validates existing schema and returns False if absent; `collection_exists()` only checks presence. Reopen stores after external schema changes.
- `scroll(query_filter=...)` yields all matching payload records without vectors. `overwrite_payload(payload, selector)` preserves vectors. `overwrite_payloads([PayloadUpdate(id, payload), ...], batch_size=256)` batches distinct complete per-point payload replacements and returns the number submitted (not an existence count). It also never creates a collection. `delete(selector)` and payload updates accept native `PointIdsList` or `FilterSelector`.
- Use native Qdrant filters, including ranges and nested boolean clauses. Compose mandatory tenant scope with user filters using AND for every applicable operation; tenant isolation and globally unique point IDs are application responsibilities.
- Declare payload indexes before ingestion. Local storage needs no indexes; remote index mismatches require an explicit migration.
- The caller owns the client. Keep `open_qdrant` open across the server lifespan, inject its client, and let the context close it. Stores do not close borrowed clients or use global caches.
- Keep fingerprinting, chunking, sync orchestration and source record lookup in the application. Batched upsert is retryable with stable IDs, not atomic across batches.

See [setup](setup.md) for storage settings. The native `store.client` remains available for advanced Qdrant operations.
