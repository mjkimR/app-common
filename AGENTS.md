# AGENTS.md - Guide for AI Assistants

This repository contains a **highly modular framework for FastAPI-based development**, split into independent `uv workspace` packages designed to isolate concerns and allow standalone usage.

---

## Tooling & Commands

We use **just** as the primary command runner and task orchestrator.

> [!IMPORTANT]
> **The `justfile` is the Single Source of Truth (SSOT).**
> Always read the `justfile` directly to inspect available targets, aliases, parameter defaults, and implementation
> scripts. Do not rely on stale hardcoded command examples.
> *Note: Our linting, checking, and format recipes use `set -e` internally to fail immediately if any individual module encounters an error. There is no silent exit.*

### Installing `just`

Use the provided scripts to install it automatically:

- **macOS / Linux**: `./scripts/install-just.sh`
- **Windows**: `scripts\install-just.bat`

### Scripts & Shared Infrastructure

- Keep the `justfile` as a thin orchestration layer.
- Put shared or complex shell logic in `scripts/` and source helpers such as `scripts/_lib.sh`.
- Supported modules are managed as separate Python packages inside the workspace.

### Quick Command Reference

- **List commands**: `just` or `just --list`
- **Initialize all modules**: `just init`
- **Initialize one module**: `just init <module-name>` (e.g., `just init app-layer-base`)
- **Initialize with extras**: `just init-dev` or `just init-dev <module-name>`
- **Lint & format all modules**: `just lint`
- **Lint & format one module**: `just lint <module-name>` (e.g., `just lint app-file-storage`)
- **Type check all modules**: `just check`
- **Type check one module**: `just check <module-name>`
- **Run tests**: `just test` — every module on SQLite, no Docker needed. Container-backed tests are deselected, so this is the fast one you run constantly.
- **Run tests on PostgreSQL**: `just test-pg` — **needs Docker**. `SELECT ... FOR UPDATE SKIP LOCKED` is a no-op on SQLite, so this is the only run that verifies the outbox's row locking.
- **Run container-backed tests**: `just test-docker` — **needs Docker**. Adds the tests marked `docker`, e.g. the S3 storage contract against a real MinIO (mocked aiobotocore hid three real bugs; see `app-file-storage/tests/integrate/`).
- **Run targeted tests**: `uv run pytest <package-directory>/tests` (e.g., `uv run pytest app-layer-base/tests`)
- **Run tests with coverage**: `just test-cov` or `just test-cov <module-name>` — per-package + combined report, HTML in `htmlcov/`. Includes the container-backed tests (uses Docker if present) so it does not under-report. Coverage is a finder, not a target: there is no `fail_under` and it is deliberately not a CI gate.

CI runs all three test legs on every push, so anything deselected locally is still verified before merge. A test that needs a real backend must be marked `docker` (or gated behind `--db-type postgres`) — never left to silently skip.

---

## Repository Map & Architecture

### 1. Workspace Structure

The repository is fully modularized into discrete workspace packages:

- **`app-layer-base/`**: The core foundation layer (FastAPI, SQLAlchemy, Pydantic).
    - `base/`: Domain scaffolding including CRUD patterns, Repositories, UseCases, and Service Hooks.
    - `core/`: Database engines, transaction management, logging middleware, and traceback filtering.
    - `utils/`: Common time and type hint utilities.
    - `config_util.py` & `config.py`: Environment settings loaders and general app settings.
- **`app-file-storage/`**: Standalone adapter for local and AWS S3 storage client operations.
- **`app-vector-store/`**: Standalone adapter for Qdrant vector database storage and search.
- **`app-http-client/`**: Standalone light-weight HTTP client adapter based on `httpx`.
- **`app-ai-catalog/`**: AI model factories, LangChain AI clients, and LiteLLM adapters.
- **`app-prebuilt-user/`**: Prebuilt authentication, signup, and user management controllers, services, and models.
- **`app-prebuilt-outbox/`**: Prebuilt Transactional Outbox pattern engine for reliable event messaging.
- **`app-tools/`**: CLI tool for scaffolding new modular features.
    - Usage: `uv run app-tools create-code feature --name <Name>`
    - `create_code/templates/feature/`: the generated feature skeleton, one `*.tmpl` per emitted file.
- **`app-helper/`**: Standalone developer CLI for git-diff prompt building and clipboard helpers.
    - Usage: `app-helper prompt commit|review`, `app-helper copy-diff`
    - Ported from the maintainer's `~/.zshrc` functions (`gic`, `gir`, `copydiff`), which remain the upstream originals.

Every package keeps its source in `src/<package_name>/` and its tests in `tests/unit/` (plus `tests/integrate/` where present). Tests never live under `src/`. Each package owns its own pytest config (`[tool.pytest.ini_options]`), so its rootdir is the package directory — there is deliberately no workspace-wide `pythonpath`.

Shared test fixtures live in `app_layer_base.testing` and are loaded as a pytest plugin, never off `sys.path`:

```python
# <package>/tests/conftest.py  (must be the top-level conftest)
pytest_plugins = ["app_layer_base.testing.db"]
```

That plugin owns `--db-type`, the `real_commit` marker, and the `session` / `session_maker` / `async_engine` / `is_postgres` fixtures. Never copy a `tests/fixtures/db.py` into a package; a `tests/` directory shared over `sys.path` collides on the name `tests` and silently shadows whichever copy loads first.

### 2. Core Architecture

- **Layered Flow**: `API (Router) -> UseCase -> Service -> Repository`.
- **Service Hooks**: All business logic should be implemented as service hooks defined in `app-layer-base`. A hook is a standalone object implementing one or more of the protocols in `base/services/hooks.py` (`CreateHook`, `UpdateHook`, `DeleteHook`, `GetHook`, `GetMultiHook`); a service declares them as one ordered `hooks = (...)` tuple. The executor enters each hook's context in that order, runs the repository call, then unwinds in reverse — hooks never call `super()` and never call each other.
- **DI**: Extensive use of FastAPI's `Depends` and `Annotated[T, Depends(func)]`.
- **Settings Composition**: Each package owns its own `Settings` class. There is no central aggregator — `app_layer_base.config` holds only the base `AppSettings`, and an application composes the per-package settings it actually needs, so importing one adapter never drags in another's dependencies.

---

## CRITICAL CONSTRAINTS (DO NOT IGNORE)

1. **Surgical Edits**: Only modify what is requested. Avoid unrelated refactors.
2. **DI Consistency**: Use `Annotated[T, Depends(func)]` for FastAPI dependencies.
3. **Testing**: Always check if new code requires tests. Run tests in the modified package before finalizing.
4. **No Emojis**: Do not use emojis in commit messages, code comments, or docs.
5. **Security**: Never commit `.env` or log sensitive PII/secrets.
6. **Git Commit**: Do not execute `git commit` commands or perform commits automatically unless explicitly requested by the user.

---

## Further Reading

- Detailed guides are available in `skill/app-base-developer-skill/docs/`.
- Key reference: `app_layer_base_guide.md` for architecture and hooks.
