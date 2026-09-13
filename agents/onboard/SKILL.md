---
name: app-onboard
description: One-time onboarding guide for bootstrapping new FastAPI projects with app-common packages, environment setup, and skill installation.
---

# app-common Project Onboarding Guide

This guide is designed for AI coding assistants (Antigravity, Claude Code, Cursor, Codex) to bootstrap a new or existing FastAPI project using `app-common` modular packages.

> **Note for Agents**: This is a one-time onboarding workflow. Do not save or keep this skill in the project's local skills directory. Once onboarding is complete, only the day-to-day skills for installed packages will be installed into `.agents/skills/`.

---

## Onboarding Procedure

Follow these sequential phases to set up the project:

### Phase 1: Requirements Interview
Before writing code or running commands, ask the developer:
1. **Database Backend**: PostgreSQL (`asyncpg`) or SQLite (`aiosqlite`)?
2. **Object Storage**: AWS S3, MinIO, Local filesystem, or None?
3. **Vector Database / RAG**: Qdrant required?
4. **AI Models**: LiteLLM model router & catalog (`catalog.yml`) required?
5. **Prebuilt Modules**:
   - User authentication & JWT login (`app-prebuilt-user`)?
   - Transactional Outbox pattern for domain events (`app-prebuilt-outbox`)?
   - Pooled HTTP client (`app-http-client`)?
6. **Testing & Frontend**:
   - Test foundation (`app-testing-base`) with Pytest base classes and DI resolver?
   - Web frontend using Svelte 5 and `@app-common/ui-base`?

---

### Phase 2: Install Packages via `uv`

Initialize the project with `uv` if not already initialized:
```bash
uv init
```

#### 1. Core Foundation (Always Required)
```bash
# Foundational layered architecture
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/base/app-layer-base"

# Zero-dependency structured error protocol
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/base/app-error"

# Code scaffolding CLI (dev dependency)
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=tools/app-tools" --dev

# Test foundation & fixtures (dev dependency, recommended)
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/base/app-testing-base" --dev

# Database driver
# For PostgreSQL:
uv add asyncpg
# For SQLite:
uv add aiosqlite
```

#### 2. Selected Adapters & Prebuilts (Install Only Selected)
```bash
# File Storage (S3 / MinIO / Local FS)
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/adapters/app-file-storage"

# Vector Store (Qdrant)
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/adapters/app-vector-store"

# HTTP Client Pool
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/adapters/app-http-client"

# AI Model Catalog
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/adapters/app-ai-catalog"

# User Management & JWT Authentication
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/prebuilt/app-prebuilt-user"
uv add python-multipart

# Transactional Outbox Pattern
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/prebuilt/app-prebuilt-outbox"
```

---

### Phase 3: Project Skeleton & Lifespan Setup

Create the application entry point `app/main.py` with composed lifespans for selected adapters:

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

# Import lifespans for selected adapters only:
# from app_file_storage import lifespan_file_storage
# from app_http_client import lifespan_http_client
# from app_vector_store import lifespan_vector_store

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    # Compose adapter contexts here if used
    yield

app = FastAPI(title="My Application", lifespan=app_lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
```

Create `.env.example` containing required database and selected adapter variables:
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mydb
# or for SQLite: sqlite+aiosqlite:///./app.db

# If app-prebuilt-user was selected:
SECRET_KEY=change_this_to_a_random_hex_key
FIRST_USER_EMAIL=admin@example.com
FIRST_USER_PASSWORD=change_this_password
```

---

### Phase 4: Download Agent Skills Matching Installed Packages

Download the skills from the same immutable release as the packages you installed:

```bash
# Replace <release-tag> with the same tag used above.
curl -sSL https://raw.githubusercontent.com/mjkimR/app-common/<release-tag>/scripts/install-skills.sh | bash -s -- --auto --ref=<release-tag>

# Or for Claude Code (.claude/skills):
curl -sSL https://raw.githubusercontent.com/mjkimR/app-common/<release-tag>/scripts/install-skills.sh | bash -s -- --auto --ref=<release-tag> claude
```

This reads `pyproject.toml` and installs only the skills you actually use (`app-backend-core`, `app-file-storage`, etc.) into your workspace.

---

### Phase 5: Verification & First Feature Scaffolding

Test the setup and verify everything works:
```bash
# Verify app launches
uv run uvicorn app.main:app --port 8000 &
PID=$!
sleep 2
curl http://localhost:8000/health
kill $PID

# Scaffold your first backend CRUD feature using app-tools
uv run app-tools create-code feature --name Item

# Or scaffold a Svelte 5 web feature (if working on frontend)
uv run app-tools create-code web-feature --name Item
```

Onboarding is complete! The project is now configured with a lean codebase and tailored agent skills.
