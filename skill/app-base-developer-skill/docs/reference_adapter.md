# Standalone Adapter Modules Guide

Each adapter is a fully modularized **standalone package** in the workspace. It installs on its own (via `git+...#subdirectory=`) and pulls in only its own dependencies — no bloat. Because each package installs independently, **its README is the canonical reference** (install, env-var table, public API, lifespan wiring). This page is only the index and the shared conventions.

## Shared house-style

Multi-backend adapters (`app-file-storage`, `app-vector-store`) follow the same layering so they are interchangeable and predictable:

`interface → registry → factory → instance → providers`

- **interface**: the abstract client/provider contract consumers depend on.
- **registry**: maps a provider enum (from `config.py`) to a provider implementation.
- **factory / instance**: builds and memoizes the concrete client from settings.
- **providers**: the concrete backends (e.g. S3 vs Local, Qdrant).
- **lifespan**: an async context manager that opens/closes the client with the app lifecycle — resolve the client from dependency injection or lifespan state, never instantiate it ad-hoc.

A single-backend adapter collapses this to just `instance` + `lifespan` (e.g. `app-http-client`, which has no registry/providers because there is only one backend).

Configuration is per-package Pydantic `BaseSettings`; there is no central aggregator (see [Core, Config, AI & Utils Reference](./reference_core_config.md#2-configuration-app_layer_baseconfig--per-package-settings)).

## Adapters

| Package | Namespace | Backends | Canonical reference |
|---|---|---|---|
| `app-file-storage` | `app_file_storage` | AWS S3 / MinIO (`aiobotocore`), Local FS | [README](../../../app-file-storage/README.md) |
| `app-vector-store` | `app_vector_store` | Qdrant (`qdrant-client`, `langchain-qdrant`) | [README](../../../app-vector-store/README.md) |
| `app-http-client` | `app_http_client` | Shared `httpx.AsyncClient` pool | [README](../../../app-http-client/README.md) |

Quick entry points:

- **File Storage** — `from app_file_storage import get_storage_client` → `await client.upload_file(key, data)`. The S3 provider needs `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_BUCKET_NAME`.
- **Vector Store** — `from app_vector_store import get_vector_store_client` → `await provider.create_vector_store(...)`. Requires `app-ai-catalog` to resolve the embedding client and its dimension at instantiation.
- **HTTP Client** — reuse a single connection pool across the app to avoid fd exhaustion; resolve it from DI / lifespan state rather than constructing a new `httpx.AsyncClient()`.
