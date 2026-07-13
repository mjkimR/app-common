# app-layer-base

The foundational domain layer for FastAPI backends in this workspace. It provides a generic, hook-driven CRUD stack on SQLAlchemy 2.0 (async) + Pydantic v2, plus the core infrastructure (database/transactions, middlewares, logging, exceptions) that the other packages build on.

## Installation

```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-layer-base"
```

## What it provides

- **`base/`** — the domain building blocks:
  - `repos/` — `BaseRepository[Model, Create, Put, Patch]`: async CRUD with pagination, bulk ops, soft/hard delete, composite-PK handling.
  - `services/` — `Base*ServiceMixin` + composable hook objects (unique constraints, nested-resource ownership, user auditing, domain events, exists checks, delete-response detail). A service declares one ordered `hooks` tuple; the executor enters each hook's context in that order and unwinds in reverse, so no hook can break the chain for the others.
  - `usecases/` — transaction-wrapping `Base*UseCase` classes.
  - `deps/` — FastAPI dependency factories for declarative filtering, ordering and pagination.
  - `schemas/`, `models/`, `exceptions/` — `PaginatedList`, `DomainEvent` (CloudEvents), mixins (`UUIDMixin`, `TimestampMixin`, `AuditMixin`, `SoftDeleteMixin`), and RFC 7807 error handlers.
- **`core/`** — async engine + `AsyncTransaction`, middlewares (CORS, request-id, query-counter, security headers, timeout), loguru config, traceback filtering.
- **`config.py`** — `AppSettings` and the lazy env-file loader.
- **`testing/`** — pytest fixtures and DI helpers for code built on this package. See below.

## Testing against app-layer-base

Anything built on this package needs the same things to test: a session wired to the
engine accessors the app code calls, table cleanup between tests, and a way to
reconstruct `Annotated[T, Depends()]` trees without an app or a request.

```bash
uv add --dev "app-layer-base[testing] @ git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-layer-base"
```

The fixtures are a pytest plugin. Enable them from the **top-level `conftest.py`** of a
test suite — pytest only honours `pytest_plugins` there:

```python
# tests/conftest.py
pytest_plugins = ["app_layer_base.testing.db"]
```

That gives you:

| | |
|---|---|
| `--db-type sqlite\|postgres` | SQLite in-memory by default; `postgres` stands up a container (needs Docker) |
| `session`, `session_maker`, `async_engine` | session bound to the test engine, with `get_async_engine` / `get_session_maker` patched |
| `is_postgres` | skip-guard for tests that only mean something on a real PostgreSQL |
| `@pytest.mark.real_commit` | opt out of savepoint isolation when another connection must see committed rows |

By default PostgreSQL tests are isolated with a savepoint that is rolled back, so nothing
reaches disk. SQLite always commits for real (aiosqlite mishandles nested savepoints) and
the tables are emptied afterwards.

The backends are not interchangeable: SQLite parses `FOR UPDATE SKIP LOCKED` and ignores
it, and its `StaticPool` shares one connection. Anything asserting on row locking or two
concurrent transactions must run on PostgreSQL and skip elsewhere.

Also exported from `app_layer_base.testing`: `resolve_dependency` / `MockRequest` for
building a service or usecase straight from its dependency tree, `clean_db_after_test`,
`random_email`, `random_string`.

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

Projects follow a decoupled flow: **API (Router) → UseCase → Service → Repository**. Business logic goes in service hooks rather than in routers. New feature modules can be scaffolded with [`app-tools`](../app-tools/README.md).

See the developer guides for the full picture:

- [Architecture & Service Hooks Guide](../skill/app-base-developer-skill/docs/app_layer_base_guide.md)
- [Base Module Reference](../skill/app-base-developer-skill/docs/reference_base.md)
- [Core, Config & Utils Reference](../skill/app-base-developer-skill/docs/reference_core_config.md)

## Public API

`AppSettings`, `get_app_settings`, and env helpers (`get_project_root`, `get_env_file_path`, `load_env`, ...) are exported at the top level; the domain classes are imported from their submodules (e.g. `from app_layer_base.base.repos.base import BaseRepository`). Test support is under `app_layer_base.testing` and needs the `testing` extra — see [Testing against app-layer-base](#testing-against-app-layer-base).
