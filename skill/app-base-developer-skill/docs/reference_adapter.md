# Standalone Adapter Modules Guide

This document explains the adapters provided in our workspace packages. Each adapter is fully modularized as a standalone package inside the workspace, allowing independent imports and zero-dependency bloat.

---

## 1. Event Broker (`app-event-broker`)

### Summary
Manages event streaming, publishing, and subscribing via standard message brokers.

### Components
- **Import Namespace**: `app_event_broker`
- **Modules**: `factory.py`, `instance.py`, `lifespan.py`
- **Underlying Stack**: `faststream`, `faststream[rabbit]`, `faststream[redis]`
- **Usage**:
  - Retrieve the active instance from the FastAPI dependency or global `get_event_broker` to publish events.
- **Precautions**: Ensure `EVENT_BROKER_URL` is set in configuration. Lifespan handlers must be linked to the FastAPI application to manage the connection pool cleanly.

---

## 2. File Storage (`app-file-storage`)

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

## 3. NoSQL Database (`app-nosql-db`)

### Summary
Adapts Document NoSQL databases like MongoDB or Firebase Firestore to clean repository and service patterns.

### Components
- **Import Namespace**: `app_nosql_db`
- **Providers**: `providers/mongodb.py` (via `motor`), `providers/firestore.py` (via `google-cloud-firestore`).
- **Precautions**: Switch providers transparently by updating your configuration, but verify index structures and specific query constraints when switching back-ends.

---

## 4. Vector Store (`app-vector-store`)

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

## 5. HTTP Client (`app-http-client`)

### Summary
Asynchronous HTTP Client management utilizing a single connection pool.

### Components
- **Import Namespace**: `app_http_client`
- **Modules**: `instance.py`, `lifespan.py` (manages `httpx.AsyncClient` lifespan).
- **Usage**: Reuse a single connection pool across the application to prevent fd exhaustion.
- **Precautions**: Always resolve the client from the dependency injection or lifespan state rather than instantiating a new `httpx.AsyncClient()` manually.