---
name: app-common-contributor
description: Guide for developing app-common itself. Covers multi-db testing (SQLite, Postgres, Docker), package isolation, and release tagging.
---

# app-common-contributor

This skill guides engineers and agents working directly on the codebase of `app-common` (modifying packages under `packages/`, tools under `tools/`, or scripts under `scripts/`).

---

## 1. Workspace Boundaries & Architectural Constraints

1. **Strict Package Isolation**:
   - `packages/base/app-error` has **zero third-party dependencies**. It uses only Python standard library (`dataclasses`, `enum`, `typing`). Never add external dependencies to it.
   - Adapters (`packages/adapters/*`) must **never depend on each other**. For example, `app-file-storage` cannot import `app-vector-store`.
   - Settings are strictly decentralized. Each package owns its own `Settings` class inheriting from `pydantic_settings.BaseSettings`. There is no central settings aggregator.
2. **Git-Based Package Releases**:
   - Packages are consumed via git URLs: `git+https://github.com/mjkimR/app-common.git@vX.Y.Z#subdirectory=packages/...`.
   - Never publish packages to PyPI.
   - When releasing, bump `version` across all package `pyproject.toml` files simultaneously to match the repository git tag.

---

## 2. Multi-Tier Testing Strategy

Always run the appropriate test target before finalizing code changes:

| Command | Backends / Environment | What it Verifies |
|---|---|---|
| `just test` | **SQLite (in-memory)** | Fast unit test cycle. Container-backed tests are automatically deselected. No Docker required. |
| `just test-pg` | **PostgreSQL (Testcontainers, Docker)** | Row-locking mechanics. `SELECT ... FOR UPDATE SKIP LOCKED` is a no-op on SQLite; this run verifies the Outbox concurrency guarantees. |
| `just test-docker` | **MinIO / Real Containers (Docker)** | Multi-backend storage contract tests. Mocked tests hid real bugs in the past; contract tests against real MinIO prevent regressions. |
| `just test-cov` | **All backends + Coverage** | Generates detailed coverage report in `htmlcov/`. |

### Test Plugin Conventions
- **Never copy fixture files** (e.g. `fixtures/db.py`) into package test directories. Doing so creates `sys.path` shadowing collisions.
- Always load shared fixtures through the pytest plugin:
  ```python
  # <package>/tests/conftest.py
  pytest_plugins = ["app_layer_base.testing.db"]
  ```
- This plugin provides `session`, `session_maker`, `async_engine`, and `is_postgres` fixtures.
- Mark container-dependent tests with `@pytest.mark.docker`.

---

## 3. Linting & Static Typing

Before submitting changes, all checks must pass with zero errors:

```bash
# Format and fix lint errors across all packages
just lint

# Run Pyright static type checking across all package src/ directories
just check
```

- Pyright checks `src/` directories.
- Ensure strict type annotations on all public functions, classes, and parameters.

---

## 4. Adding a New Package or Adapter

When adding a new modular package:
1. Create directory structure:
   ```
   packages/<category>/<package-name>/
   ├── pyproject.toml
   ├── README.md
   ├── src/<package_name>/
   │   ├── __init__.py
   │   ├── py.typed
   │   └── ...
   └── tests/
       ├── conftest.py
       └── unit/
   ```
2. Register the module in `justfile`:
   - Add module name to `lint`, `check`, and `lint-check` loops.
3. Register the module in `scripts/_lib.sh`:
   - Add to `AVAILABLE_MODULES`, `resolve_module`, `resolve_module_path`, and `validate_module`.
4. Run `uv sync --package <package-name>` and verify with `just check <package-name>`.
