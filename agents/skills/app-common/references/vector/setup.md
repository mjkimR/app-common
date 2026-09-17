# app-vector-store Setup & Configuration

```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/adapters/app-vector-store"
```

Only Qdrant and settings dependencies are needed. Install an embedding provider separately in the application if needed.

`QdrantSettings()` loads these variables; constructor arguments override the corresponding field. Conflicting locations are rejected, including conflicts with environment values.

| Variable | Default | Description |
|---|---|---|
| `VECTOR_DB_MODE` | required | `local`, `remote`, or `memory` |
| `VECTOR_DB_PATH` | unset | Required for local mode; forbidden otherwise |
| `VECTOR_DB_URL` | unset | Required HTTP(S) URL for remote mode; forbidden otherwise |
| `VECTOR_DB_API_KEY` | unset | Optional secret for remote mode only |
| `VECTOR_DB_TIMEOUT` | `10` | Positive remote request timeout in seconds |

Use `QdrantSettings(mode="memory")` for explicitly ephemeral tests. Use one client per local path; use a remote server when multiple processes share storage. Missing configuration never silently falls back to memory.

The old `VECTOR_DB_PROVIDER`, `VECTOR_DB_QDRANT_*`, catalog model-name lookup and global lifespan/factory APIs have been removed. No compatibility layer is provided.
