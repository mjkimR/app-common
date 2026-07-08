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
- **Run tests**: `just test` (runs tests inside `app-prebuilt-user` / `app-prebuilt-outbox`)
- **Run targeted tests**: `uv run pytest <package-directory>/tests` (e.g., `uv run pytest app-layer-base/tests`)

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

### 2. Core Architecture

- **Layered Flow**: `API (Router) -> UseCase -> Service -> Repository`.
- **Service Hooks**: All business logic should be implemented using `BaseService` hooks (e.g., `_context_create`, `_pre_create_hook`) defined in `app-layer-base`.
- **DI**: Extensive use of FastAPI's `Depends` and `Annotated[T, Depends(func)]`.
- **Settings Composition**: Settings are kept within their respective packages and lazy-loaded dynamically by `app-base/config` to avoid dependency bloat.

---

## CRITICAL CONSTRAINTS (DO NOT IGNORE)

1. **Surgical Edits**: Only modify what is requested. Avoid unrelated refactors.
2. **DI Consistency**: Use `Annotated[T, Depends(func)]` for FastAPI dependencies.
3. **Testing**: Always check if new code requires tests. Run tests in the modified package before finalizing.
4. **No Emojis**: Do not use emojis in commit messages, code comments, or docs.
5. **Security**: Never commit `.env` or log sensitive PII/secrets.
6. **Git Commit**: NEVER execute `git commit` commands or perform commits automatically. Committing changes must be left entirely to the user.

---

## Further Reading

- Detailed guides are available in `skill/app-base-developer-skill/docs/`.
- Key reference: `app_base_guide.md` for architecture and hooks.
