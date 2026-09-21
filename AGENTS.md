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
- **UI Package Commands**:
  - `just init-ui` — install root ESLint tooling and Svelte UI library dependencies
  - `just check-ui` — enforce file-size limits and type check UI library with `svelte-check`
  - `just build-ui` — build Svelte library to `dist/` with `@sveltejs/package`
  - `just test-eslint` — test the shared frontend size preset and bounded exceptions
- **Run tests**: `just test` — every module on SQLite, no Docker needed. Container-backed tests are deselected, so this is the fast one you run constantly.
- **Run tests on PostgreSQL**: `just test-pg` — **needs Docker**. `SELECT ... FOR UPDATE SKIP LOCKED` is a no-op on SQLite, so this is the only run that verifies the outbox's row locking.
- **Run container-backed tests**: `just test-docker` — **needs Docker**. Adds the tests marked `docker`, e.g. the S3 storage contract against a real MinIO (mocked aiobotocore hid three real bugs; see `app-file-storage/tests/integrate/`).
- **Run targeted tests**: `uv run pytest <package-directory>/tests` (e.g., `uv run pytest app-layer-base/tests`)
- **Run tests with coverage**: `just test-cov` or `just test-cov <module-name>` — per-package + combined report, HTML in `htmlcov/`. Includes the container-backed tests (uses Docker if present) so it does not under-report. Coverage is a finder, not a target: there is no `fail_under` and it is deliberately not a CI gate.

CI runs all three test legs on every push, so anything deselected locally is still verified before merge. A test that needs a real backend must be marked `docker` (or gated behind `--db-type postgres`) — never left to silently skip.

### Releases

Packages are consumed as git dependencies (`git+...@<ref>#subdirectory=<path-to-package>`), never published to PyPI. A release is a repo-level tag:

1. Bump `version` in every package's `pyproject.toml`, root `package.json`, and `packages/ui/app-ui-base/package.json` (and their npm locks) to match the tag (one repo version across all packages — they ship together).
2. Tag the commit and push it: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. CI runs lint / type-check / all three test legs on the tag; only if they pass does the `release` job create a GitHub Release with generated notes.

Consumers should pin a tag (`rev = "vX.Y.Z"`) instead of `rev = "main"`, which floats and can break silently.

---

## Repository Map & Architecture

### 1. Workspace Structure

The repository is structured into organized category directories under `packages/` and `tools/`:

- **`packages/base/`**:
    - **`app-error/`**: Zero-dependency core error protocol and agent advisory primitives (`Actor`, `Retry`, `ActionMode`, `Advisory`, `AppError`).
    - **`app-layer-base/`**: The core foundation layer (FastAPI, SQLAlchemy, Pydantic).
        - `base/`: Domain scaffolding including CRUD patterns, Repositories, UseCases, and Service Hooks.
        - `core/`: Database engines, transaction management, logging middleware, and traceback filtering.
        - `utils/`: Common time and type hint utilities.
        - `config_util.py` & `config.py`: Environment settings loaders and general app settings.
    - **`app-testing-base/`**: The testing foundation for FastAPI, SQLAlchemy, and Pytest.
        - Pytest plugin (`app_testing_base.plugin`) providing `session`, `async_engine`, `client` (FastAPI test client), `resolve_dependency` (DI resolver), assertion helpers, and deterministic seeding primitives (`random_string`, `random_email`, `utc_now`).
- **`packages/adapters/`**:
    - **`app-file-storage/`**: Standalone adapter for local and AWS S3 storage client operations.
    - **`app-vector-store/`**: Standalone adapter for Qdrant vector database storage and search.
    - **`app-http-client/`**: Standalone light-weight HTTP client adapter based on `httpx`.
    - **`app-ai-catalog/`**: AI model factories, LangChain AI clients, and LiteLLM adapters.
- **`packages/prebuilt/`**:
    - **`app-prebuilt-user/`**: Prebuilt authentication, signup, and user management controllers, services, and models.
    - **`app-prebuilt-search/`**: DB-backed semantic search and explicit incremental indexing over existing application data.
    - **`app-prebuilt-outbox/`**: Prebuilt Transactional Outbox pattern engine for reliable event messaging.
- **`packages/transports/`**:
    - **`app-mcp/`**: Protocol-neutral MCP tool registry and authorization boundary; concrete transports live outside this core package.
- **`packages/ui/`**:
    - **`app-ui-base/`**: Svelte 5 foundational UI library (`@app-common/ui-base`).
        - `components/`: Accessible, responsive components (`AppShell`, `PageHeader`, `EmptyState`, `StatusBadge`, `LoadingSpinner`, `ThemeToggle`).
        - `stores/`: Reactive Svelte 5 stores (`sessionStore`, `themeStore`).
        - `ui/`: Core atomic primitives (`Button`, `Card`, `Input`).
        - `styles/`: Semantic Tailwind design tokens (`tokens.css`) and class merging utility (`cn`).
- **`tools/`**:
    - **`app-tools/`**: CLI tool for scaffolding new modular features and managing local dev symlinks.
        - Usage (Backend Feature Scaffolding): `uv run app-tools create-code feature --name <Name>`
        - Usage (Web Feature Scaffolding): `uv run app-tools create-code web-feature --name <Name>`
        - Usage (Local Dev Linking): `uv run app-tools dev link`, `dev unlink`, `dev status`
        - `create_code/templates/`: generated feature skeletons for backend and Svelte 5 web features.
- **`packages/tooling/eslint-config/`**: Shared frontend size preset, exported by the
  root npm package `@app-common/eslint-config`. Follow the `ui/structure` guide:
  resolve size errors by meaningful splitting or an exact-file, reasoned, finite
  ceiling. Do not suppress the rule or automatically increase ceilings to pass.

Every package keeps its source in `src/<package_name>/` and its tests in `tests/unit/` (plus `tests/integrate/` where present). Tests never live under `src/`. Each package owns its own pytest config (`[tool.pytest.ini_options]`), so its rootdir is the package directory — there is deliberately no workspace-wide `pythonpath`.

Shared test fixtures live in `app_testing_base` (and historically `app_layer_base.testing`) and are loaded as a pytest plugin, never off `sys.path`:

```python
# <package>/tests/conftest.py  (must be the top-level conftest)
pytest_plugins = ["app_testing_base.plugin"]
```

That plugin owns `--db-type`, the `real_commit` marker, the `session` / `session_maker` / `async_engine` / `is_postgres` fixtures, and the `client` fixture. Never copy a `tests/fixtures/db.py` into a package; a `tests/` directory shared over `sys.path` collides on the name `tests` and silently shadows whichever copy loads first.

### 2. Core Architecture

- **Layered Flow (CRUD stack)**: `API (Router) -> UseCase -> Service -> Repository`. Non-CRUD consumers may keep domain-specific repositories and caller-owned transactions; use explicit import boundaries and the HTTP-only test plugin without adopting CRUD scaffolding.
- **Non-CRUD commands**: `app_layer_base.application` provides typed `Command`, `execute_command` and `TransactionScope`. Use feature `commands.py` / `schemas.py` with optional `usecases.py`; read `backend/commands`. Enforce the opt-in command architecture rules and registry/scope contracts from `app_testing_base.application`. Consistent agent-written feature structure and reviewability are goals alongside reuse.
- **Service Hooks (CRUD stack)**: All business logic should be implemented as service hooks defined in `app-layer-base`. A hook is a standalone object implementing one or more of the protocols in `base/services/hooks.py` (`CreateHook`, `UpdateHook`, `DeleteHook`, `GetHook`, `GetMultiHook`); a service declares them as one ordered `hooks = (...)` tuple. The executor enters each hook's context in that order, runs the repository call, then unwinds in reverse — hooks never call `super()` and never call each other.
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
7. **Local Package Linking (`app-tools dev`)**: When modifying `app-common` packages from a downstream consumer repository, use `uv run app-tools dev link` to temporarily symlink local packages. Never hardcode local paths into `pyproject.toml` or `package.json`. When finished, always run `uv run app-tools dev unlink` and verify clean state with `uv run app-tools dev status`.

---

## Skills

| Situation | Skill |
|---|---|
| Using or introducing app-common packages, testing, UI, local linking, or updates | `app-common` |
| Contributing to app-common itself (package isolation, multi-db tests, releases) | `app-common-contributor` |

The consumer entry point routes to topic guides. Run `app-tools guide` for project-specific
recommendations, `app-tools guide list --all` for all topics, and `app-tools guide show <topic>`
for one document. Standalone `app-error` does not imply the backend architecture rules.

Canonical consumer documents live in `agents/skills/app-common/` and ship inside app-tools.
`tools/app-tools/src/app_tools/guide_data` points there; edit the canonical files only.
`agents/apm.yml` exposes this collection to Microsoft APM without `.apm/`.
The contributor skill remains under `agents/dev-skills/`.

- In app-common: read `agents/dev-skills/app-common-contributor/SKILL.md` directly.
- In consumers: use `apm.yml` and `apm install`; see `agents/README.md`.
- For offline consumers: provision the complete APM skill bundle before network isolation.
- When releasing, update the guide catalog version alongside package versions. Tests check parity.
