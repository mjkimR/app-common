# app-common

A personal monorepo containing highly modularized packages and developer CLI tools designed to accelerate, standardize, and scale application development across FastAPI-based backend systems.

---

## Workspace Core Packages

This repository is built as a `uv workspace` divided into focused, standalone packages. You can import only what you need, avoiding heavy third-party dependency bloat.

### 1. Foundation Packages
- **[app-error](./packages/base/app-error/README.md)**: Zero-dependency structured exception protocols, agent advisory payloads (`Actor`, `Retry`, `ActionMode`, `Advisory`), and CLI error formatting.
- **[app-layer-base](./packages/base/app-layer-base/README.md)**: Foundational domain layer with generic CRUD repository base classes, transaction-aware usecases, mixin-based service hooks, database traceback filters, loguru configuration, time/type helper utilities, and base application settings.
- **[app-testing-base](./packages/base/app-testing-base/README.md)**: Standard testing foundation for FastAPI, SQLAlchemy, and Pytest. Pytest plugin providing database engines, session fixtures, DI resolver (`resolve_dependency`), HTTP client (`AsyncClientWithJson`), base test classes (`UnitTest`, `IntegrationTest`, `E2ETest`), and assertion utilities.

### 2. Standalone Adapters
Each adapter isolates a specific technology stack and can be imported independently:
- **[app-file-storage](./packages/adapters/app-file-storage/README.md)**: Support for Local and AWS S3 object storage clients.
- **[app-vector-store](./packages/adapters/app-vector-store/README.md)**: Support for Qdrant vector databases, seamlessly integrated with `app-ai-catalog`.
- **[app-http-client](./packages/adapters/app-http-client/README.md)**: Lightweight asynchronous HTTP client wrapper based on `httpx`.

### 3. Standalone AI & Prebuilt Services
- **[app-ai-catalog](./packages/adapters/app-ai-catalog/README.md)**: AI embedding/LLM factory clients leveraging LiteLLM and LangChain.
- **[app-prebuilt-user](./packages/prebuilt/app-prebuilt-user/README.md)**: Fully scaffolding-ready user authentication, JWT login flow, and user profile management.
- **[app-prebuilt-outbox](./packages/prebuilt/app-prebuilt-outbox/README.md)**: A production-ready Transactional Outbox pattern engine for guaranteed message delivery.

### 4. UI Library & Developer Productivity
- **[app-ui-base](./packages/ui/app-ui-base/README.md)**: Agent-First Svelte 5 foundational UI library (`@app-common/ui-base`) providing layout shell (`AppShell`), atomic UI primitives (`Button`, `Card`, `Input`), reactive state stores (`sessionStore`, `themeStore`), and Tailwind design tokens.
- **[app-tools](./tools/app-tools/README.md)**: Developer CLI tool to automatically generate layered CRUD code (backend features and Svelte 5 web features) and manage local development symlinks (`app-tools dev`).

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
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=packages/base/app-layer-base"

# Add only the File Storage adapter
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=packages/adapters/app-file-storage"

# Add the developer CLI tool
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=tools/app-tools" --dev
```

---

## Developer Skills & Agent Assets

Modular, agent-neutral skills are available under [`agents/`](./agents/README.md) to assist developers and AI assistants:

- **[`app-backend-core`](./agents/skills/app-backend-core/SKILL.md)**: Layered architecture (Router → UseCase → Service → Repository → Model/Schema), Service Hooks, feature scaffolding with `app-tools`, and structured error advisories (`app-error`).
- **[`app-testing`](./agents/skills/app-testing/SKILL.md)**: FastAPI test foundation with `app-testing-base` (unit/integrate/e2e test cases, deterministic seeders, DI resolver, and assertion helpers).
- **[`app-file-storage`](./agents/skills/app-file-storage/SKILL.md)**: AWS S3, MinIO, and Local filesystem object storage.
- **[`app-vector-store`](./agents/skills/app-vector-store/SKILL.md)**: Qdrant vector database integration.
- **[`app-http-client`](./agents/skills/app-http-client/SKILL.md)**: Shared connection-pooled httpx client.
- **[`app-ai-catalog`](./agents/skills/app-ai-catalog/SKILL.md)**: LiteLLM model routing and LangChain embedding integration.
- **[`app-prebuilt-user`](./agents/skills/app-prebuilt-user/SKILL.md)**: User auth, JWT login flow, and admin CRUD.
- **[`app-prebuilt-outbox`](./agents/skills/app-prebuilt-outbox/SKILL.md)**: Transactional Outbox pattern engine for guaranteed domain event delivery.
- **[`app-svelte-ui`](./agents/skills/app-svelte-ui/SKILL.md)**: Svelte 5 Runes + SvelteKit + Tailwind + shadcn architecture and Type-Safe API binding.
- **[`app-common-contributor`](./agents/dev-skills/app-common-contributor/SKILL.md)**: Monorepo package boundaries, multi-tier testing (SQLite, PostgreSQL, Docker), and contributor conventions.


To link skills:
```bash
# In downstream apps (auto-detects installed app-* packages):
./agents/link-skills.sh --auto

# In app-common (links all skills + contributor dev-skills):
just link-skills --dev
```

### AI Agent Onboarding
To bootstrap a new FastAPI project from scratch with an AI agent, give the agent this GitHub link:
> `https://github.com/mjkimR/app-common/blob/main/agents/onboard/SKILL.md`



