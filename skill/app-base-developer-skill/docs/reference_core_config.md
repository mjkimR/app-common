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

## 2. Configuration (`app_layer_base.config` / per-package settings)

### Summary
Uses Pydantic Settings (`BaseSettings`) to strictly validate and load environment variables. Each package owns its own independent settings class — there is no central aggregator; `app-layer-base` only provides the app-level `AppSettings`.

### Components
- **`app-layer-base/src/app_layer_base/config.py`**: `AppSettings` — `APP_ENV`, `DATABASE_URL`, the `LOG_*` group (`LOG_PATH`, `LOG_LEVEL`, `LOG_JSON_FORMAT`, `LOG_SIMPLE_TRACEBACK`, `LOG_TRACEBACK_WHITELIST`), and the `CORS_*` group (`CORS_ALLOWED_ORIGINS`, `CORS_ALLOW_ORIGIN_REGEX`, `CORS_ALLOW_CREDENTIALS`).
- **`app-layer-base/src/app_layer_base/config_util.py`**: `ConfigLoader` that parses YAML and resolves `${ENV_VAR}` variables if needed.
- **Per-adapter settings**: Each adapter package (`app-file-storage`, `app-vector-store`, `app-http-client`) defines and loads its own settings class in its own `config.py`, fully independently. See each package's README for its env-var table.
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
- **Canonical reference**: [`app-ai-catalog/README.md`](../../../app-ai-catalog/README.md) — install, env vars, and full public API.

---

## 4. Utils Module (`app_layer_base.utils`)

### Summary
General purpose helper functions. Lives in the `app-layer-base` package.

### Components
- **`time_util.py`**: Helper functions for parsing, formatting, and standardizing timezone-aware datetime objects (defaults to UTC).
- **`type_hint.py`**: Provides strict generic typing aliases (`SeqOrOneOrNone`, etc.) utilized extensively by Repositories and Services.
- **Precautions**: Always use timezone-aware datetimes when interacting with the database `TimestampMixin`.