# app-base

Common module package for personal app development (FastAPI-based)

## Features

| Module | Description |
|--------|-------------|
| `base` | CRUD service/repository patterns, exception handling, schema mixins |
| `adapter` | File Storage (Local, S3), Vector Store (Qdrant) adapters |
| `ai` | LLM/Embedding model factories (LangChain-based) |
| `config` | Common configuration management (Pydantic Settings) |
| `core` | Logging, DB engine, middlewares |
| `utils` | Utility functions |

## Installation

```bash
# Basic installation
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-base"

# Optional dependencies
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-base[s3]"      # S3 storage
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-base[qdrant]"  # Qdrant vector DB
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-base[ai]"      # LangChain AI
```

## Requirements

- Python >= 3.12
