# app-backend-core Setup & Configuration

## Installation

Add the core foundation package and the developer tooling, pinned to one app-common commit:

```bash
# Foundational domain framework (brings devkit-advisory, whose devkit.advisory errors it raises)
uv add "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=packages/base/app-layer-base"

# `devkit app` commands and the app-common devkit bundle (dev dependency)
uv add --dev "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=tools/app-tools"
```

uv does not follow the sources of Git dependencies: copy the `devkit` and `devkit-advisory`
entries of app-common's root `[tool.uv.sources]` at that commit into the project's own
`[tool.uv.sources]`. List both as dependencies too (a dev dependency is enough): uv applies a source only to a direct dependency, and an unrelated `devkit` project exists on PyPI. Then run `uv sync` and `uv run devkit sync`.

## Environment Specification & Config

To inspect required and optional environment variables for any configuration:

```bash
uv run devkit app env-spec --type app
```

### Core Database Settings
| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | SQLAlchemy async database connection string (e.g. `postgresql+psycopg://...` or `sqlite+aiosqlite://...`) |
| `DB_ECHO` | `false` | Enable SQL query echo logging |
| `DB_POOL_SIZE` | `5` | Connections each process keeps pooled (server databases; SQLite ignores it). Multiply by workers and instances against the server's connection limit |
| `DB_MAX_OVERFLOW` | `10` | Extra connections each process may open under load |
