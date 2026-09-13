# app-prebuilt-outbox Setup & Configuration

## Installation
```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/prebuilt/app-prebuilt-outbox"
```

## Prerequisites & Database
- Relies on PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` for concurrency and multi-worker safety. (SQLite is supported for local tests, but row locks are no-ops).
- The `Outbox` table model is exported from `app_prebuilt_outbox.models`. Run database migrations or ensure the table is created at startup.
