# AGENTS.md - Guide for AI Assistants

This repository contains a **common framework for FastAPI-based development** (`app-base`) and its corresponding *
*developer CLI** (`app-tools`).

## Tooling & Commands

We use **just** as a command runner.
Use the provided scripts to install it automatically:

- **macOS / Linux**: `./scripts/install-just.sh`
- **Windows**: `scripts\install-just.bat`

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

## Tooling & Commands

We use **just** as a command runner.

- **Initialize**: `just init` (or `just init-dev` for all extras)
- **Lint & Format**: `just lint` (Runs Ruff)
- **Test**: `just test` (Runs Pytest)
- **Type Check**: `pyright` (Runs manually or via IDE)

## CRITICAL CONSTRAINTS (DO NOT IGNORE)

1. **Surgical Edits**: Only modify what is requested. Avoid unrelated refactors.
2. **Type Safety**: Maintain strict type hinting. Use `pyright` to verify.
3. **DI Consistency**: Use `Annotated[T, Depends(func)]` for FastAPI dependencies.
4. **Testing**: Always check if new code requires tests. Run `just test` before finalizing.
5. **No Emojis**: Do not use emojis in commit messages or code comments.
6. **Security**: Never commit `.env` or log sensitive PII/secrets.

## Further Reading

- Detailed guides are available in `skill/app-base-developer-skill/docs/`.
- Key reference: `app_base_guide.md` for architecture and hooks.
