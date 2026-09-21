# app-vector-store

A small async Qdrant adapter. Applications supply vectors; the adapter owns collection validation, storage, payload operations and filtered search. No AI catalog, LangChain, model registry, or global store cache is required.

## Installation

```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/adapters/app-vector-store"
```

## Storage and client ownership

```python
from app_vector_store import QdrantSettings, open_qdrant

# Choose exactly one mode. A missing mode or conflicting location raises an error.
settings = QdrantSettings(mode="local", path="./data/vectors")
# QdrantSettings(mode="remote", url="http://localhost:6333")  # optional api_key
# QdrantSettings(mode="memory")  # explicitly ephemeral


async def example():
    async with open_qdrant(settings) as client:
        ...
```

`open_qdrant` closes the client even when the body raises. For a server, keep this context open for its application lifespan and inject the client into request handlers. A store borrows the client and never closes it. `create_qdrant_client(settings)` is also available when the caller handles `await client.close()` itself. Share one client per local path; embedded storage is not a multi-process server. Use remote Qdrant for shared deployments.

`QdrantSettings()` reads environment variables. Explicit constructor fields take precedence for the same field; contradictory fields from the environment are rejected rather than silently selecting another location.

| Variable | Default | Description |
|---|---|---|
| `VECTOR_DB_MODE` | required | `local`, `remote`, or `memory` |
| `VECTOR_DB_PATH` | unset | Required only for local mode |
| `VECTOR_DB_URL` | unset | Required HTTP(S) URL only for remote mode |
| `VECTOR_DB_API_KEY` | unset | Optional remote secret |
| `VECTOR_DB_TIMEOUT` | `10` | Positive remote request timeout, seconds |

## Store and independent embeddings

```python
from qdrant_client import models
from app_vector_store import QdrantVectorStore, VectorPoint


async def index_and_search(client, embedder):
    # embedder is application-owned: FastEmbed, an API SDK, or your own provider.
    store = QdrantVectorStore(
        client,
        "documents",
        dimension=384,
        embedding_id="my-model@revision1:preprocessing-v1",
    )
    await store.ensure_payload_indexes({"project": models.PayloadSchemaType.KEYWORD})
    vectors = await embedder.embed_documents(["Document text"])
    await store.upsert([VectorPoint(id=1, vector=vectors[0], payload={"project": "alpha"})])

    project_filter = models.Filter(
        must=[
            models.FieldCondition(key="project", match=models.MatchValue(value="alpha")),
        ]
    )
    query_vector = await embedder.embed_query("What is this document about?")
    hits = await store.search(query_vector, query_filter=project_filter, limit=10)
    return [(hit.id, hit.score, hit.payload) for hit in hits]
```

Embedding methods in the example are the application's own interface, not package APIs. Keep document/query embedding operations separate so each model can apply its appropriate input formatting. The adapter accepts only computed dense vectors and never downloads models or makes embedding API calls.

`embedding_id` is persisted as the collection's single named vector. It must identify the model, revision and preprocessing/chunking version that define the embedding space. Existing collections must match this name, dimension and distance (default cosine); mismatches raise `CollectionMismatchError`. Even equal-dimension model changes require a new collection and reindexing. The adapter cannot infer which model actually produced an input vector; the caller must supply the correct identity.

Writes through `upsert` and explicit `ensure_collection()`/`ensure_payload_indexes()` create missing collections. Search, scroll, delete and payload replacement never create them. `validate_collection()` returns False if absent and validates existing schema; `collection_exists()` only checks presence. Recreate store instances after external collection changes. Anonymous-vector or multi-vector collections are intentionally outside this adapter's contract. Use the exposed native client for advanced Qdrant operations.

## Filters, payloads and incremental indexing

- `search(vector, query_filter=..., limit=10, score_threshold=None, offset=0)` returns native Qdrant scored points, including IDs and payloads, without vectors.
- `upsert(points, batch_size=256)` replaces vectors and payloads by stable integer or UUID IDs, returning the number submitted. Batches are not one transaction; retry with the same IDs after partial network failure.
- `scroll(query_filter=..., batch_size=256)` is an async iterator over all matching records/payloads, without vectors. Use it for fingerprint inventories.
- `delete(selector)` accepts `models.PointIdsList` or `models.FilterSelector`.
- `overwrite_payload(payload, selector)` replaces matching payloads without recomputing vectors.
- `ensure_payload_indexes({field: schema})` creates missing remote indexes and rejects conflicting definitions; it does not drop indexes. Embedded Qdrant supports filters without indexes, so this operation is a no-op there after collection validation.

Filters are native `models.Filter`, supporting nested AND/OR/NOT, ranges, arrays and other Qdrant conditions. Tenant scoping is application-owned: combine required scope and user filters with AND, including for scroll, delete and payload updates. A filter selector with an empty filter matches all points. IDs must also be unique across tenants within a collection.

Corpus discovery, text/chunking, source-of-truth reads, fingerprint policy and incremental-sync orchestration stay in the application. No domain fields such as `project`, `kind` or `doc_id` are built into the adapter.

This API replaces the old model-name factory and global FastAPI lifespan APIs without a compatibility layer. `app-ai-catalog` remains an independent package but is no longer a dependency.

## Batch payload replacement

Use `overwrite_payloads([PayloadUpdate(point_id, payload), ...], batch_size=256)`
for different complete payloads per point. It uses Qdrant batch updates, preserves
vectors, removes omitted payload fields and never creates a missing collection.
The return value counts submitted updates, not existing matched points. Partial
remote failure can leave earlier batches applied; repeat stable replacements to
reconcile. Scope authorization and selecting the correct point IDs remain caller
responsibilities, as with `overwrite_payload`.
