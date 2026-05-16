# app-base

Common module package for personal app development (FastAPI-based)

## Features

| Module    | Description                                                         |
|-----------|---------------------------------------------------------------------|
| `base`    | CRUD service/repository patterns, exception handling, schema mixins |
| `adapter` | File Storage (Local, S3), Vector Store (Qdrant) adapters            |
| `ai`      | LLM/Embedding model factories (LangChain-based)                     |
| `config`  | Common configuration management (Pydantic Settings)                 |
| `core`    | Logging, DB engine, middlewares                                     |
| `utils`   | Utility functions                                                   |

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

## Documentation

For comprehensive guides on architecture, using service hooks, and detailed component references, please refer to the **Developer Skills** documentation located in the root repository:

- **[app-base Developer Guide](../skill/app-base-developer-skill/docs/app_base_guide.md)**: Core architecture and service hook tutorials.
- **[Component References](../skill/app-base-developer-skill/docs/)**: Detailed API-level documentation for `base`, `adapter`, `core`, and `config` modules.
