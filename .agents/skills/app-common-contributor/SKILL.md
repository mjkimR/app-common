---
name: app-common-contributor
description: Guide for developing app-common itself. Covers multi-db testing (SQLite, Postgres, Docker), package isolation, and release tagging.
---

# app-common-contributor

This skill guides engineers and agents working directly on the codebase of `app-common` (modifying packages under `packages/`, tools under `tools/`, or scripts under `scripts/`).

---

## 1. Workspace Boundaries & Architectural Constraints

1. **Strict Package Isolation**:
   - Errors are `devkit.advisory.AdvisoryError` subclasses. A package that raises them declares `devkit>=0.1,<0.2`; the root `pyproject.toml` pins devkit's Git revision for the whole workspace, and moving it is a release note for consumers.
   - Adapters (`packages/adapters/*`) must **never depend on each other**. For example, `app-file-storage` cannot import `app-vector-store`.
   - Settings are strictly decentralized. Each package owns its own `Settings` class inheriting from `pydantic_settings.BaseSettings`. There is no central settings aggregator.
2. **Git-Based Package Releases**:
   - Packages are consumed via git URLs pinned to a commit: `git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=packages/...`; consumers move with `devkit app update`.
   - Never publish packages to PyPI.
   - When releasing, bump `version` across all package `pyproject.toml` files, the guide catalog and both `bundle.toml` files simultaneously to match the repository git tag, then run `just sync-agents`.

---

## 2. Multi-Tier Testing Strategy

Always run the appropriate test target before finalizing code changes:

| Command | Backends / Environment | What it Verifies |
|---|---|---|
| `just test` | **SQLite (in-memory)** | Full local unit and integration coverage. Container-backed tests are automatically deselected. No Docker required. |
| `just test-pg` | **PostgreSQL (Testcontainers, Docker)** | Row-locking mechanics. `SELECT ... FOR UPDATE SKIP LOCKED` is a no-op on SQLite; this run verifies the Outbox concurrency guarantees. |
| `just test-docker` | **MinIO / Real Containers (Docker)** | Multi-backend storage contract tests. Mocked tests hid real bugs in the past; contract tests against real MinIO prevent regressions. |
| `just test-cov` | **All backends + Coverage** | Generates detailed coverage report in `htmlcov/`. |

### Test Plugin Conventions
- **Never copy fixture files** (e.g. `fixtures/db.py`) into package test directories. Doing so creates `sys.path` shadowing collisions.
- Always load shared fixtures through the pytest plugin:
  ```python
  # <package>/tests/conftest.py
pytest_plugins = ["app_testing_base.plugin"]
  ```
- This plugin provides `session`, `session_maker`, `async_engine`, and `is_postgres` fixtures.
- Mark container-dependent tests with `@pytest.mark.docker`.

---

## 3. Linting & Static Typing

`just lint` and `just lint-check` run Ruff and then `devkit rules check`, which loads the
app-common architecture rules from the deployed bundle (`RULE-app-*`) and devkit's
built-in rules (Markdown links among them). `RULE-app-adapter-dependency` rejects sibling
adapter imports. Use `just rules-check packages tools` (or `uv run devkit rules check
--format json <paths>`) for locations and fixes. Existing compatibility exceptions must
carry `# arch: ignore[RULE-app-<rule>] -- reason` on the diagnostic line. These import
checks do not replace dependency-manifest review or the design constraints above.

The rule logic lives in `tools/app-tools/src/app_tools/architecture/`; the bundle's
`rules/architecture.py` only declares the rule classes. After editing anything under
`tools/app-tools/src/app_tools/bundle/` or `tools/app-common-dev/`, run `just sync-agents`
and commit `.devkit/installation.json`, `AGENTS.md` and the projected skills with the
source change; never edit `.devkit/managed/`, `.agents/skills/` or `.claude/skills/`.

Before submitting changes, all checks must pass with zero errors:

```bash
# Format and fix lint errors across all packages
just lint

# Run Pyright static type checking across all package src/ directories
just check
```

- Pyright checks `src/` directories.
- Ensure strict type annotations on all public functions, classes, and parameters.

For frontend work, `just init-ui` installs the root shared ESLint tooling and UI
dependencies; `just check-ui` runs size checks and Svelte type checks. Changes to the
shared preset also require `just test-eslint`. The root npm manifest exports
`@app-common/eslint-config` from `packages/tooling/eslint-config/`; include its
version when updating all packages for a release.

Follow the consumer `ui/structure` guide: split oversized files by responsibility,
or record an exact path, rationale, and finite ceiling. Do not disable the rule or
automatically raise a ceiling to pass a check. Keep this policy in the canonical
consumer guides under `tools/app-tools/src/app_tools/bundle/skills/app-common/references/ui/`.

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
4. Run `just init` (always the whole workspace: `uv sync --package` would strip the other members from the shared `.venv`) and verify with `just check <package-name>`.

---

## 5. Testing with Downstream Projects (`devkit app dev`)

When verifying changes against a downstream consumer project before publishing a release, **never edit the consumer's `pyproject.toml` or `package.json` to point to local file paths** (this prevents dirty git diffs or accidental commits of local paths).

Instead, run `devkit app dev` inside the consumer project to temporarily link its installed packages to this local `app-common` repository:

### Workflow

1. **Link local app-common**:
   Run in the consumer project root:
   ```bash
   uv run devkit app dev link
   ```
   - Automatically searches for `app-common` across `-1 to +1 depth` (e.g. `../app-common`, sibling folders, child/parent folders).
   - Backs up installed packages in `.venv/lib/python*/site-packages/` and `node_modules/` as `*.bak`.
   - Creates symlinks to `app-common/.../src/*` and `app-common/packages/ui/*`.
   - Preserves `.dist-info` metadata so `uv` does not re-sync or overwrite the environment.
   - Entry points come from that preserved metadata: the consumer must already run an app-tools version that declares the `devkit.commands` and `devkit.bundles` entry points. A linked `app_tools` makes the checkout's bundle the deployed one after `uv run devkit sync`.

2. **Develop and Test**:
   - Edit `app-common` source code directly.
   - Run tests in the downstream consumer project to verify the changes.
   - Switch to `app-common` and run `just lint`, `just check`, and `just test` to verify package health.

3. **[CRITICAL] Always Unlink Before Finishing**:
   Once changes are verified and pushed/released, **always unlink** to restore the consumer repository to its original installed state:
   ```bash
   uv run devkit app dev unlink
   ```

4. **Verify Clean State**:
   Confirm that all packages are `installed` again (the command exits 1 otherwise):
   ```bash
   uv run devkit app dev status
   ```
