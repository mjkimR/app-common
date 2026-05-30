# Core, Config, AI & Utils Modules Guide

This document covers the core setup, configuration management, AI model factories, and utility modules across the modular workspace packages.

---

## 1. Core Module (`app_layer_base.core`)

### Summary
The `core` module initializes foundational aspects like the database engine, transaction middleware, CORS, logging, and security setups. It lives in the `app-layer-base` package.

### Database (`app_layer_base.core.database`)
- **`engine.py`**: Initializes the SQLAlchemy `AsyncEngine` and `async_sessionmaker`.
- **`transaction.py` / `deps.py`**: Manages the database session lifecycle. Often utilized in FastAPI dependencies to inject `AsyncSession` into UseCases or Services.

### Middlewares (`app_layer_base.core.middlewares`)
- **`request_id_middleware.py`**: Injects a unique `X-Request-ID` into every HTTP request context for log tracing.
- **`cors_middleware.py`**: Sets up Cross-Origin Resource Sharing. Note: if `*` is used for origins, `allow_credentials` is strictly set to `False` for security.
- **`timeout_middleware.py` & `query_counter.py`**: Used for monitoring request durations and the number of database queries executed per request.

### Logging (`app_layer_base.core.log`)
- Provides a centralized `logger` instance. Always use this instead of the standard `print()` or `logging.getLogger()`.

---

## 2. Configuration (`app_base.config` / per-package settings)

### Summary
Uses Pydantic Settings (`BaseSettings`) to strictly validate and load environment variables. Each standalone adapter package owns its own settings class. The `app-base` package aggregates them all for convenience.

### Components
- **`app-layer-base/src/app_layer_base/config.py`**: `AppSettings` contains variables like `ENV`, `DEBUG`, `CORS_ALLOWED_ORIGINS`.
- **`app-layer-base/src/app_layer_base/config_util.py`**: `ConfigLoader` that parses YAML and resolves `${ENV_VAR}` variables if needed.
- **Per-adapter settings**: Each adapter package (`app-file-storage`, `app-event-broker`, `app-nosql-db`, `app-vector-store`, `app-http-client`) defines its own settings class in its own `config.py` or `settings.py`. These are lazily loaded by `app-base/src/app_base/config/` when the full framework is used.
- **Usage**:
  ```python
  from app_layer_base.config_util import ConfigLoader

  config = ConfigLoader.load("config.yaml")
  ```
- **Precautions**: Ensure `.env` is loaded before instantiating settings. Missing required variables will cause a `ValidationError` at startup.

---

## 3. AI Module (`app_ai_catalog`)

### Summary
Provides factory patterns for instantiating LangChain LLM and Embedding models based on configurations. Lives in the standalone `app-ai-catalog` package.

### Components
- **`app_ai_catalog.models.schemas`**: Defines standard schemas for AI Models (`AIModelItem`) and Groups.
- **`app_ai_catalog.models.factory_llm`**: Instantiates Chat models (OpenAI, Google Gemini, Anthropic) via LangChain using mapped arguments.
- **`app_ai_catalog.models.factory_embedding`**: Instantiates Embedding models.
- **`app_ai_catalog.litellm`**: LiteLLM-based adapters for model-agnostic completions.
- **Usage**:
  ```python
  from app_ai_catalog.models.factory import get_llm_factory

  llm = get_llm_factory().create_model(config)
  response = await llm.ainvoke("Hello!")
  ```
- **Precautions**: Relies on LangChain integrations. Ensure optional dependencies (`[ai]`) are installed (`langchain-openai`, `langchain-google-genai`). Missing dependencies will raise an `ImportError`.

---

## 4. Utils Module (`app_layer_base.utils`)

### Summary
General purpose helper functions. Lives in the `app-layer-base` package.

### Components
- **`time_util.py`**: Helper functions for parsing, formatting, and standardizing timezone-aware datetime objects (defaults to UTC).
- **`type_hint.py`**: Provides strict generic typing aliases (`SeqOrOneOrNone`, etc.) utilized extensively by Repositories and Services.
- **Precautions**: Always use timezone-aware datetimes when interacting with the database `TimestampMixin`.