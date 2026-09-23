# app-backend-core Setup & Configuration

## Installation

Add the core foundation packages and developer CLI tool:

```bash
# Foundational domain framework
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/base/app-layer-base"

# Zero-dependency structured error protocol
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/base/app-error"

# Code scaffolding CLI (dev dependency)
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=tools/app-tools" --dev
```

## Environment Specification & Config

To inspect required and optional environment variables for any configuration:

```bash
uv run app-tools get-env-spec --type database_sqlalchemy
```

### Core Database Settings
| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | — | SQLAlchemy async database connection string (e.g. `postgresql+psycopg://...` or `sqlite+aiosqlite://...`) |
| `DB_ECHO` | `false` | Enable SQL query echo logging |
| `DB_POOL_SIZE` | `5` | Connections each process keeps pooled (server databases; SQLite ignores it). Multiply by workers and instances against the server's connection limit |
| `DB_MAX_OVERFLOW` | `10` | Extra connections each process may open under load |
