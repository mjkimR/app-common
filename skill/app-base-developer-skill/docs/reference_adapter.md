# Standalone Adapter Modules Guide

This document explains the adapters provided in our workspace packages. Each adapter is fully modularized as a standalone package inside the workspace, allowing independent imports and zero-dependency bloat.

---

## 1. File Storage (`app-file-storage`)

### Summary
Unified interface for asynchronous object storage operations (uploading, downloading, metadata reading).

### Components
- **Import Namespace**: `app_file_storage`
- **Providers**: `providers/local.py` (Local File System), `providers/s3.py` (AWS S3 / MinIO via `aiobotocore`).
- **Interface**: `FileStorageClient`.
- **Usage**:
  ```python
  from app_file_storage import get_storage_client
  
  client = get_storage_client()
  await client.upload_file("destination_key", bytes_data)
  ```
- **Precautions**: The S3 provider requires proper environment settings (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_S3_BUCKET_NAME`).

---

## 2. Vector Store (`app-vector-store`)

### Summary
Integrates with vector databases for semantic search and AI embedding storage.

### Components
- **Import Namespace**: `app_vector_store`
- **Providers**: `providers/qdrant.py` (utilizes `qdrant-client` and `langchain-qdrant`).
- **Interface**: `VectorStoreProvider`.
- **Usage**:
  ```python
  from app_vector_store import get_vector_store_client
  
  provider = get_vector_store_client()
  store = await provider.create_vector_store(collection_name="docs", model_name="text-embedding-3-small")
  ```
- **Precautions**: The Qdrant provider requires the `app-ai-catalog` package to automatically fetch embeddings during vector store instantiation.

---

## 3. HTTP Client (`app-http-client`)

### Summary
Asynchronous HTTP Client management utilizing a single connection pool.

### Components
- **Import Namespace**: `app_http_client`
- **Modules**: `instance.py`, `lifespan.py` (manages `httpx.AsyncClient` lifespan).
- **Usage**: Reuse a single connection pool across the application to prevent fd exhaustion.
- **Precautions**: Always resolve the client from the dependency injection or lifespan state rather than instantiating a new `httpx.AsyncClient()` manually.