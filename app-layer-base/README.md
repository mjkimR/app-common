# app-layer-base

The foundational domain layer for FastAPI backends in this workspace. It provides a generic, hook-driven CRUD stack on SQLAlchemy 2.0 (async) + Pydantic v2, plus the core infrastructure (database/transactions, middlewares, logging, exceptions) that the other packages build on.

## Installation

```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-layer-base"
```

## What it provides

- **`base/`** — the domain building blocks:
  - `repos/` — `BaseRepository[Model, Create, Put, Patch]`: async CRUD with pagination, bulk ops, soft/hard delete, composite-PK handling.
  - `services/` — `Base*ServiceMixin` + composable hook mixins (unique constraints, nested-resource ownership, user auditing, domain events, exists checks) chained via `super()`.
  - `usecases/` — transaction-wrapping `Base*UseCase` classes.
  - `deps/` — FastAPI dependency factories for declarative filtering, ordering and pagination.
  - `schemas/`, `models/`, `exceptions/` — `PaginatedList`, `DomainEvent` (CloudEvents), mixins (`UUIDMixin`, `TimestampMixin`, `AuditMixin`, `SoftDeleteMixin`), and RFC 7807 error handlers.
- **`core/`** — async engine + `AsyncTransaction`, middlewares (CORS, request-id, query-counter, security headers, timeout), loguru config, traceback filtering.
- **`config.py`** — `AppSettings` and the lazy env-file loader.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `local` | Environment name (drives environment-aware behavior) |
| `DATABASE_URL` | — | SQLAlchemy async database URL |
| `LOG_LEVEL` | `INFO` | Log level |
| `LOG_PATH` | — | Log output path |
| `LOG_JSON_FORMAT` | `false` | Emit structured JSON logs |
| `CORS_ALLOWED_ORIGINS` | `[]` | Allowed CORS origins |
| `CORS_ALLOW_ORIGIN_REGEX` | `None` | Regex of allowed CORS origins |

## Architecture

Projects follow a decoupled flow: **API (Router) → UseCase → Service → Repository**. Business logic goes in `BaseService` hooks rather than in routers. New feature modules can be scaffolded with [`app-tools`](../app-tools/README.md).

See the developer guides for the full picture:

- [Architecture & Service Hooks Guide](../skill/app-base-developer-skill/docs/app_base_guide.md)
- [Base Module Reference](../skill/app-base-developer-skill/docs/reference_base.md)
- [Core, Config & Utils Reference](../skill/app-base-developer-skill/docs/reference_core_config.md)

## Public API

`AppSettings`, `get_app_settings`, and env helpers (`get_project_root`, `get_env_file_path`, `load_env`, ...) are exported at the top level; the domain classes are imported from their submodules (e.g. `from app_layer_base.base.repos.base import BaseRepository`).
