# app-vector-store Setup & Configuration

## Installation
```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/adapters/app-vector-store"
```

> **Note**: Requires `app-ai-catalog` to be configured (`catalog.yml`), as embedding models and dimensions are resolved from it.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `VECTOR_DB_PROVIDER` | `qdrant` | Backend provider: `none` \| `qdrant` |
| `VECTOR_DB_QDRANT_URL` | `http://localhost:6333` | Qdrant server URL |
| `VECTOR_DB_QDRANT_API_KEY` | — | API key for Qdrant |
