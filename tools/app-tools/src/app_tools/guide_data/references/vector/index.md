# app-vector-store

LangChain-compatible `VectorStore` adapter backed by Qdrant with automatic embedding model resolution.

> For package installation and environment variables, see [setup.md](./setup.md).

## Lifespan Wiring

Register the lifespan to handle store cache cleanup on application shutdown:

```python
from fastapi import FastAPI
from app_vector_store import lifespan_vector_store

app = FastAPI(lifespan=lifespan_vector_store)
```

## Usage

```python
from app_vector_store import get_vector_store


async def search_similar(query: str):
    # Resolves embedding model and vector dimension automatically from catalog.yml
    store = await get_vector_store(collection_name="docs", model_name="text-embedding-3-small")
    return await store.asimilarity_search(query, k=4)
```

- Collections are created automatically if missing, using the dimension specified in `catalog.yml`.
- Store instances are cached per `(collection, model)`.
