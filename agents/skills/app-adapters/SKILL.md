---
name: app-adapters
description: Guide for integrating standalone infrastructure adapters in app-common (app-file-storage, app-vector-store, app-http-client, app-ai-catalog). Covers shared adapter house-style (interface -> registry -> factory -> instance -> providers), lifespan composition, decentralized Pydantic settings, and dependency injection.
---

# app-adapters

This skill covers the integration of standalone infrastructure adapters into FastAPI applications. Each adapter is fully modularized and pulls in only its own dependencies.

## Shared House-Style

Multi-backend adapters (`app-file-storage`, `app-vector-store`) follow a consistent architecture:

`interface → registry → factory → instance → providers`

- **interface**: Abstract client/provider contract consumed by your code.
- **registry**: Maps backend provider enums to concrete implementations.
- **factory / instance**: Instantiates and memoizes singleton client instances from settings.
- **providers**: Concrete backends (e.g. S3 vs Local, Qdrant).
- **lifespan**: Async context manager managing connection initialization and cleanup.

Configuration is decentralized via per-package Pydantic `BaseSettings`. Applications only import and compose the settings they actually use.

---

## Lifespan Composition

When using multiple adapters, compose their lifespans into a single FastAPI lifespan context manager:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app_http_client import lifespan_http_client
from app_file_storage import lifespan_file_storage
from app_vector_store import lifespan_vector_store

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    async with lifespan_http_client(app):
        async with lifespan_file_storage(app):
            async with lifespan_vector_store(app):
                yield

app = FastAPI(lifespan=app_lifespan)
```

---

## 1. File Storage (`app-file-storage`)

Provides an asynchronous `FileStorageClient` with support for AWS S3, MinIO, and Local Filesystem.

### Installation
```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=packages/adapters/app-file-storage"
```

### Environment Variables
- `FS_PROVIDER`: `none` | `local` | `s3` (default: `none`)
- **Local (`FS_PROVIDER=local`)**:
  - `FS_LOCAL_BUCKET_NAME`: Base filesystem path for storage root.
- **S3 / MinIO (`FS_PROVIDER=s3`)**:
  - `FS_S3_BUCKET_NAME`: Target bucket (e.g. `my-bucket`)
  - `FS_S3_ACCESS_KEY` & `FS_S3_SECRET_KEY`: Credentials.
  - `FS_S3_ENDPOINT_URL`: Endpoint URL (omit for AWS S3, specify for MinIO).
  - `FS_S3_REGION_NAME`: AWS region (optional).
  - `FS_S3_AUTO_CREATE_BUCKET`: `true` / `false`.

### Usage
```python
from app_file_storage import get_file_storage_client

async def save_avatar(user_id: str, content: bytes):
    client = get_file_storage_client()
    key = f"avatars/{user_id}.png"
    await client.upload_file(file_data=content, file_name=key, content_type="image/png")
    url = await client.get_presigned_url(file_name=key, expiration=3600)
    return url
```

---

## 2. Vector Store (`app-vector-store`)

Provides LangChain-compatible `VectorStore` instances backed by Qdrant, automatically integrating with `app-ai-catalog` for embeddings.

### Installation
```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=packages/adapters/app-vector-store"
```

### Environment Variables
- `VECTOR_DB_PROVIDER`: `none` | `qdrant` (default: `qdrant`)
- `VECTOR_DB_QDRANT_URL`: URL to Qdrant cluster (default: `http://localhost:6333`)
- `VECTOR_DB_QDRANT_API_KEY`: API key if authentication is enabled.

### Usage
```python
from app_vector_store import get_vector_store

async def search_documents(query: str):
    # Resolves embedding dimensions from app-ai-catalog automatically
    store = await get_vector_store(collection_name="docs", model_name="text-embedding-3-small")
    docs = await store.asimilarity_search(query, k=4)
    return docs
```

---

## 3. HTTP Client (`app-http-client`)

Manages a shared, pooled `httpx` client singleton to avoid socket exhaustion and connection leaks.

### Installation
```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=packages/adapters/app-http-client"
```

### Environment Variables
- `HTTP_TIMEOUT`: Request timeout in seconds (default: `5.0`)
- `HTTP_MAX_CONNECTIONS`: Max pooled connections (default: `100`)
- `HTTP_MAX_KEEPALIVE_CONNECTIONS`: Max idle keep-alive connections (default: `20`)
- `HTTP_KEEPALIVE_EXPIRY`: Keep-alive expiration in seconds (default: `5.0`)

### Usage
```python
from app_http_client import get_http_client, get_http_sync_client

async def call_external_api():
    client = get_http_client()  # Reuses global httpx.AsyncClient pool
    response = await client.get("https://api.external.com/v1/data")
    return response.json()
```

---

## 4. AI Catalog (`app-ai-catalog`)

YAML-configured AI model client using LiteLLM Router for completions, embeddings, and LangChain integration.

### Installation
```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=packages/adapters/app-ai-catalog"
```

### `catalog.yml` Configuration
```yaml
models:
  - name: gpt-4o
    type: llm
    litellm_params:
      model: openai/gpt-4o
      api_key: ${OPENAI_API_KEY}

  - name: text-embedding-3-small
    type: text-embedding
    litellm_params:
      model: openai/text-embedding-3-small
      api_key: ${OPENAI_API_KEY}
    model_info:
      dimension: 1536

aliases:
  - name: default-llm
    type: llm
    target: gpt-4o
```

### Usage
```python
from app_ai_catalog import AIClient

ai = AIClient() # loads catalog.yml

# Completion:
response = await ai.chat_completion(
    model="default-llm",
    messages=[{"role": "user", "content": "Hello!"}]
)

# LangChain Embeddings adapter:
embeddings = ai.get_langchain_embeddings("text-embedding-3-small")
```
