---
name: app-common-onboarding
description: Bootstrap a FastAPI project on app-common packages, from the requirements interview to the first scaffolded feature.
aliases: [new app-common project, app-common setup, fastapi project bootstrap]
---

# app-common Project Onboarding

A one-time procedure for a new or existing FastAPI project. It assumes the tooling step
of the [app-common README](https://github.com/mjkimR/app-common#use-in-a-project) is
done: `app-tools` and `devkit-agt` are dev dependencies and `uv run devkit sync` has deployed
the `app-common` bundle. Every app-common package is pinned to the same app-common
commit (`<commit>` below); never use a local path or an unpinned branch.

## Phase 1: Requirements Interview

Before writing code or running commands, ask the developer:

1. **Database backend**: PostgreSQL (`psycopg 3`) or SQLite (`aiosqlite`)?
2. **Object storage**: AWS S3, SeaweedFS, local filesystem, or none?
3. **Vector database / RAG**: is Qdrant required?
4. **AI models**: LiteLLM model router and catalog (`catalog.yml`) required?
5. **Prebuilt modules**: user authentication and JWT login (`app-prebuilt-auth`),
   transactional outbox (`app-prebuilt-outbox`), pooled HTTP client (`app-http-client`)?
6. **Testing and frontend**: test foundation (`app-testing-base`)? Svelte 5 frontend on
   `@app-common/ui-base`?

## Phase 2: Install Packages

`uv run devkit app guide list --all` lists the setup guide of every package; read the
setup guide of each selected package before adding it.

```bash
# Foundation (always)
uv add "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=packages/base/app-layer-base"
uv add --dev "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=packages/base/app-testing-base"

# Database driver: PostgreSQL or SQLite
uv add "psycopg[binary]>=3.1"
uv add aiosqlite

# Selected adapters and prebuilts only
uv add "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=packages/adapters/app-file-storage"
uv add "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=packages/adapters/app-vector-store"
uv add "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=packages/adapters/app-http-client"
uv add "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=packages/adapters/app-ai-catalog"
uv add "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=packages/prebuilt/app-prebuilt-auth"
uv add "git+https://github.com/mjkimR/app-common.git@<commit>#subdirectory=packages/prebuilt/app-prebuilt-outbox"
```

Pin every app-common package the project declares to the same commit: uv resolves their
own dependencies (other app-common packages, `devkit-agt`, `devkit-advisory`) from app-common's
sources at that commit, and two commits are a conflicting-URL error. Copy the `devkit-agt` and
`devkit-advisory` entries of app-common's root `[tool.uv.sources]` into the project's at
the same revision and list both as dependencies (a dev dependency is enough): a project's
source applies only to its direct dependencies, and a declared `devkit-agt` that nothing brings
from Git does not resolve: no package index hosts it.
`uv run devkit app update` moves all of them together later.

## Phase 3: Project Skeleton and Lifespan

Create `app/main.py` with composed lifespans for the selected adapters only:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Import lifespans for selected adapters only:
# from app_file_storage import lifespan_file_storage
# from app_http_client import lifespan_http_client
# from app_vector_store import QdrantSettings, open_qdrant


@asynccontextmanager
async def app_lifespan(app: FastAPI):
    # Compose adapter contexts here if used. For vectors, use open_qdrant(QdrantSettings())
    # and keep the yielded client on app.state for the lifetime of the application.
    yield


app = FastAPI(title="My Application", lifespan=app_lifespan)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

Create `.env.example` with the database and the selected adapters' variables;
`uv run devkit app env-spec` prints the variables the installed packages read.

```bash
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/mydb
# or for SQLite: sqlite+aiosqlite:///./app.db

# If app-prebuilt-auth was selected:
SECRET_KEY=change_this_to_a_random_hex_key
FIRST_USER_EMAIL=admin@example.com
FIRST_USER_PASSWORD=change_this_password
```

## Phase 4: Verify and Scaffold the First Feature

```bash
uv run devkit sync                # deploys the app-common skill, rules and guidance
uv run devkit add advisory:python # devkit.advisory library guide (app-common errors)
uv run devkit rules check         # architecture rules included
uv run devkit app doctor
uv run devkit app create-code feature --name Item
uv run devkit app create-code web-feature --name Item   # Svelte frontend only
```

Commit `.devkit/config.toml`, `.devkit/installation.json`, `.devkit/.gitignore`, the root
`AGENTS.md` and the projected skills under `.agents/skills/` and `.claude/skills/`, so a
fresh checkout or a cloud agent has the guidance without running a sync. Set up a fresh
clone and CI with `uv sync` and `uv run devkit sync --locked` (it restores the ignored
managed copies and fails with `RECEIPT_STALE` instead of rewriting committed files); a
plain `uv run devkit sync` is for dependency or selection changes, committed with them.
