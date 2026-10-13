# app-backend-core Setup & Configuration

## Installation

Add the core foundation package and the developer tooling, pinned to one app-common commit:

```bash
# Foundational domain framework (brings devkit-advisory, whose devkit.advisory errors it raises)
uv add "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=packages/base/app-layer-base"

# `devkit app` commands and the app-common devkit bundle (dev dependency)
uv add --dev "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=tools/app-tools"
```

uv resolves what these packages depend on, `devkit-advisory` included, from app-common's
own sources at that commit. Copy the `devkit` and `devkit-advisory` entries of app-common's
root `[tool.uv.sources]` into the project's own `[tool.uv.sources]` at the same revision
(uv rejects another) and list both as dependencies (a dev dependency is enough): a
project's source applies only to its direct dependencies, and a declared `devkit` without
one resolves from PyPI, where an unrelated project owns the name. Then run `uv sync` and
`uv run devkit sync`; later clones and CI use `uv run devkit sync --locked`.

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
