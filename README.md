# app-common

A personal monorepo containing highly modularized packages and developer CLI tools designed to accelerate, standardize, and scale application development across FastAPI-based backend systems.

---

## Workspace Core Packages

This repository is built as a `uv workspace` divided into focused, standalone packages. You can import only what you need, avoiding heavy third-party dependency bloat.

### 1. [app-layer-base](./app-layer-base/README.md)
The foundational domain layer.
- **Features**: Generic CRUD repository base class, transaction-aware usecases, mixin-based service hooks, database traceback filters, loguru configuration, time/type helper utilities, and base application settings.

### 2. Standalone Adapters
Each adapter isolates a specific technology stack and can be imported independently:
- **[app-file-storage](./app-file-storage/README.md)**: Support for Local and AWS S3 object storage clients.
- **[app-vector-store](./app-vector-store/README.md)**: Support for Qdrant vector databases, seamlessly integrated with `app-ai-catalog`.
- **[app-http-client](./app-http-client/README.md)**: Lightweight asynchronous HTTP client wrapper based on `httpx`.

### 3. Standalone AI & Prebuilt Services
- **[app-ai-catalog](./app-ai-catalog/README.md)**: AI embedding/LLM factory clients leveraging LiteLLM and LangChain.
- **[app-prebuilt-user](./app-prebuilt-user/README.md)**: Fully scaffolding-ready user authentication, JWT login flow, and user profile management.
- **[app-prebuilt-outbox](./app-prebuilt-outbox/README.md)**: A production-ready Transactional Outbox pattern engine for guaranteed message delivery.

### 4. Developer Productivity
- **[app-tools](./app-tools/README.md)**: Developer CLI tool to automatically generate layered CRUD code (Models, Schemas, Repos, Services, Routers) matching this workspace's specifications.

---

## Layered Architecture Overview

Projects built with these modules strictly adhere to a decoupled layered architecture pattern:

- **API / Router**: Manages HTTP request/response payloads, validates input via Pydantic Schemas, injects dependencies, and delegates orchestration to UseCases.
- **UseCase**: Coordinates multiple services, handles domain boundaries, and controls database transactions.
- **Service**: Executes the core business logic. Built using mixin-based hooks (`BaseService`) for a clean, extensible flow (e.g., custom hooks for uniqueness or user auditing).
- **Repository**: Generic, high-performance data access layers mapping queries to SQLAlchemy models.

---

## Dynamic Settings Composition

Rather than importing a monolithic setting block, configurations are decentralized across individual adapters (e.g., `FileStorageSettings` lives inside `app-file-storage`). 
Our lazy-loading config composition engine compiles these configurations dynamically when imported, guaranteeing zero compilation and dependency overhead when packages are used stand-alone.

---

## Quick Installation

You can easily install any standalone package directly from this repository using `uv`:

```bash
# Add only the layer base
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-layer-base"

# Add only the File Storage adapter
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-file-storage"

# Add the developer CLI tool
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-tools" --dev
```

---

## Documentation & Developer Skills

Comprehensive architectural paradigms, API mappings, and development workflows are fully documented:

- **[Architecture & Service Hooks Guide](./skill/app-base-developer-skill/docs/app_layer_base_guide.md)**: Understand the core design principles and how to customize business flows via mixin hooks.
- **[CLI Code Generation Guide](./skill/app-base-developer-skill/docs/app_tools_guide.md)**: Scaffolding a feature in seconds.
- **[Adapter Modules Mapping](./skill/app-base-developer-skill/docs/reference_adapter.md)**: Details on storage, db, broker, and http client adapter configurations.
