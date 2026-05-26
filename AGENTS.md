# AGENTS.md - Guide for AI Assistants

This repository contains a **common framework for FastAPI-based development** (`app-base`) and its corresponding
**developer CLI** (`app-tools`).

## Tooling & Commands

We use **just** as the primary command runner and task orchestrator.

> [!IMPORTANT]
> **The `justfile` is the Single Source of Truth (SSOT).**
> Always read the `justfile` directly to inspect available targets, aliases, parameter defaults, and implementation
> scripts. Do not rely on stale hardcoded command examples.

### Installing `just`

Use the provided scripts to install it automatically:

- **macOS / Linux**: `./scripts/install-just.sh`
- **Windows**: `scripts\install-just.bat`

### Scripts & Shared Infrastructure

- Keep the `justfile` as a thin orchestration layer.
- Put shared or complex shell logic in `scripts/` and source helpers such as `scripts/_lib.sh`.
- Current module names are `app-base` and `app-tools`; supported aliases are defined in `scripts/_lib.sh`.

### Quick Command Reference

- **List commands**: `just` or `just --list`
- **Initialize all modules**: `just init`
- **Initialize one module**: `just init app-base` or `just init app-tools`
- **Initialize with extras**: `just init-dev` or `just init-dev app-base`
- **Lint & format all modules**: `just lint`
- **Lint & format one module**: `just lint app-base` or `just lint app-tools`
- **Type check all modules**: `just check`
- **Type check one module**: `just check app-base` or `just check app-tools`
- **Run tests**: `just test`
- **Run targeted tests**: `just test <path>`
- **Run PostgreSQL tests**: `just test-pg` or `just test-pg <path>`

## Repository Map & Architecture

### 1. Workspace Structure

- **`app-base/`**: Core library (FastAPI, SQLAlchemy, LangChain).
    - `base/`: CRUD patterns, Repositories, Services with Hooks, UseCases.
    - `adapter/`: Providers for NoSQL (MongoDB/Firestore), Vector DB (Qdrant), File Storage (S3/Local).
    - `ai/`: LLM and Embedding factories.
- **`app-tools/`**: CLI tool for code generation and environment inspection.
    - Usage: `uv run app-tools create-code feature --name <Name>`

### 2. Core Architecture

- **Layered Flow**: `API (Router) -> UseCase -> Service -> Repository`.
- **Service Hooks**: Business logic should be implemented using `BaseService` hooks (e.g., `_context_create`,
  `_pre_create_hook`).
- **DI**: Extensive use of FastAPI's `Depends` and `Annotated`.

## CRITICAL CONSTRAINTS (DO NOT IGNORE)

1. **Surgical Edits**: Only modify what is requested. Avoid unrelated refactors.
2. **DI Consistency**: Use `Annotated[T, Depends(func)]` for FastAPI dependencies.
3. **Testing**: Always check if new code requires tests. Run `just test` before finalizing. For focused verification,
   use `just test <path>` because the recipe supports `+paths`. `test` and `test-pg` take paths, not module names.
4. **No Emojis**: Do not use emojis in commit messages or code comments.
5. **Security**: Never commit `.env` or log sensitive PII/secrets.
6. **Git Commit**: NEVER execute `git commit` commands or perform commits automatically. Committing changes must be
   left entirely to the user.

## Further Reading

- Detailed guides are available in `skill/app-base-developer-skill/docs/`.
- Key reference: `app_base_guide.md` for architecture and hooks.
