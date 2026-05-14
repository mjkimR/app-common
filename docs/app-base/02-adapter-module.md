# `app_base/adapter` Module Guide

This document explains the adapters provided in the `app-base` package. Adapters serve as interfaces to external systems like NoSQL DBs, Object Storage, Vector Stores, and Event Brokers.

---

## 1. Event Broker (`app_base.adapter.event_broker`)

### Summary
Manages event streaming and publishing.

### Components
- **`interface.py` & `factory.py`**: Defines `EventBrokerProvider`.
- **`lifespan.py`**: FastAPI lifespan manager to initialize and close the connection pool cleanly.
- **Usage**: Retrieve the active instance from the dependency or global instance to publish events defined by `EventDomainHooksMixin`.
- **Precautions**: Ensure `EVENT_BROKER_URL` is set in configuration. Connections must be closed during application shutdown to avoid memory leaks.

---

## 2. File Storage (`app_base.adapter.file_storage`)

### Summary
Unified interface for object storage operations (uploading, downloading).

### Components
- **Providers**: `local.py` (Local File System), `s3.py` (AWS S3 / MinIO).
- **Interface**: `FileStorageClient`.
- **Usage**:
  ```python
  client = get_file_storage_client()
  await client.upload_file(path, bytes_data)
  ```
- **Precautions**: When using `s3.py`, make sure `boto3` is installed and `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` are provided.

---

## 3. NoSQL Database (`app_base.adapter.nosql_db`)

### Summary
Adapts NoSQL databases like MongoDB or Firebase Firestore to a repository pattern similar to SQLAlchemy.

### Components
- **Providers**: `mongodb.py`, `firestore.py`.
- **`repository.py`**: A NoSQL equivalent of `BaseRepository`.
- **Hooks**: Specific hooks tailored for NoSQL constraints (e.g., uniqueness validation in document stores).
- **Precautions**: Query syntax heavily depends on the underlying provider. Test deeply when switching between MongoDB and Firestore.

---

## 4. Vector Store (`app_base.adapter.vector_store`)

### Summary
Integrates with vector databases for AI and embeddings using LangChain's VectorStore APIs.

### Components
- **Providers**: `qdrant.py`.
- **Interface**: `VectorStoreProvider`.
- **Usage**:
  ```python
  store = provider.create_vector_store(collection_name="docs", model_name="text-embedding-ada-002")
  ```
- **Precautions**: The Qdrant provider requires the `qdrant-client` package and correct GRPC/REST API host settings in the `VectorDBSettings` config.

---

## 5. HTTP Client (`app_base.adapter.http_client`)

### Summary
Async HTTP Client management (typically using `httpx`).

### Components
- **`instance.py` & `lifespan.py`**: Provides a managed `httpx.AsyncClient`.
- **Usage**: Ensures a single connection pool is reused across the application to improve performance.
- **Precautions**: Always use the client from the dependency injection or lifespan state rather than creating a new `httpx.AsyncClient` manually to prevent exhausting available file descriptors.