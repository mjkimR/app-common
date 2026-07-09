# app-vector-store

A standalone adapter that builds LangChain `VectorStore` instances for a configured backend. Ships a Qdrant provider and resolves embeddings automatically through [`app-ai-catalog`](../app-ai-catalog/README.md).

## Installation

```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-vector-store"
```

> Requires `app-ai-catalog` to be configured (a `catalog.yml` with the embedding model), since the vector store looks up the embedding client and its dimension from the AI catalog.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `VECTOR_DB_PROVIDER` | `qdrant` | Backend to use: `none` \| `qdrant` |
| `VECTOR_DB_QDRANT_URL` | `http://localhost:6333` | Qdrant server URL |
| `VECTOR_DB_QDRANT_API_KEY` | — | API key for Qdrant |

## Usage

Wire the lifespan (it clears the store cache on shutdown), then create a store for a collection. The `model_name` refers to an embedding model defined in your AI catalog:

```python
from fastapi import FastAPI
from app_vector_store import get_vector_store, lifespan_vector_store

app = FastAPI(lifespan=lifespan_vector_store)


async def search(query: str):
    store = await get_vector_store(collection_name="docs", model_name="text-embedding-3-small")
    return await store.asimilarity_search(query, k=4)
```

The collection is created automatically if it does not exist, using the embedding dimension resolved from the AI catalog. Stores are LRU-cached per `(collection, model)`.

## Public API

- `VectorStoreProvider` — backend interface
- `VectorStoreFactory` — wraps a provider and caches created stores
- `get_vector_store(collection_name, model_name)` — convenience accessor for a cached store
- `get_vector_store_provider()`, `get_vector_store_factory()` — lower-level accessors
- `lifespan_vector_store` — FastAPI lifespan that clears the store cache on shutdown

## See also

- [Adapter Module Reference](../skill/app-base-developer-skill/docs/reference_adapter.md) — shared adapter conventions and index.
- [Architecture & Service Hooks Guide](../skill/app-base-developer-skill/docs/app_base_guide.md) — how adapters fit the layered app.
