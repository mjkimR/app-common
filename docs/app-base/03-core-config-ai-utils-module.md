# `app_base` Core, Config, AI & Utils Modules Guide

This document covers the core setup, configuration management, AI model factories, and utility modules in `app-base`.

---

## 1. Core Module (`app_base.core`)

### Summary
The `core` module initializes foundational aspects like the database engine, transaction middleware, CORS, logging, and security setups.

### Database (`core.database`)
- **`engine.py`**: Initializes the SQLAlchemy `AsyncEngine` and `async_sessionmaker`.
- **`transaction.py` / `deps.py`**: Manages the database session lifecycle. Often utilized in FastAPI dependencies to inject `AsyncSession` into UseCases or Services.

### Middlewares (`core.middlewares`)
- **`request_id_middleware.py`**: Injects a unique `X-Request-ID` into every HTTP request context for log tracing.
- **`cors_middleware.py`**: Sets up Cross-Origin Resource Sharing. Note: if `*` is used for origins, `allow_credentials` is strictly set to `False` for security.
- **`timeout_middleware.py` & `query_counter.py`**: Used for monitoring request durations and the number of database queries executed per request.

### Logging (`core.log.py`)
- Provides a centralized `logger` instance. Always use this instead of the standard `print()` or `logging.getLogger()`.

---

## 2. Configuration (`app_base.config`)

### Summary
Uses Pydantic Settings (`BaseSettings`) to strictly validate and load environment variables.

### Components
- **`config.py`**: `AppSettings` contains variables like `ENV`, `DEBUG`, `CORS_ALLOWED_ORIGINS`.
- **`file_storage.py`, `vector_db.py`, `event_broker.py`, `nosql_db.py`**: Separate configuration classes for each adapter to keep settings modular.
- **Usage**: Load via `ConfigLoader` which parses YAML and resolves `${ENV_VAR}` variables if needed.
- **Precautions**: Ensure `.env` is loaded before instantiating settings. Missing required variables will cause a `ValidationError` at startup.

---

## 3. AI Module (`app_base.ai`)

### Summary
Provides factory patterns for instantiating LangChain LLM and Embedding models based on configurations.

### Components
- **`models.schemas.py`**: Defines standard schemas for AI Models (`AIModelItem`) and Groups.
- **`models.factory_llm.py`**: Instantiates Chat models (OpenAI, Google Gemini, Anthropic) via LangChain using mapped arguments.
- **`models.factory_embedding.py`**: Instantiates Embedding models.
- **Usage**:
  ```python
  from app_base.ai.models.factory import get_llm_factory
  llm = get_llm_factory().create_model(config)
  response = await llm.ainvoke("Hello!")
  ```
- **Precautions**: Relies on LangChain integrations. Ensure optional dependencies (`[ai]`) are installed (`langchain-openai`, `langchain-google-genai`). Missing dependencies will raise an `ImportError`.

---

## 4. Utils Module (`app_base.utils`)

### Summary
General purpose helper functions.

### Components
- **`time_util.py`**: Helper functions for parsing, formatting, and standardizing timezone-aware datetime objects (defaults to UTC).
- **`type_hint.py`**: Provides strict generic typing aliases (`SeqOrOneOrNone`, etc.) utilized extensively by Repositories and Services.
- **Precautions**: Always use timezone-aware datetimes when interacting with the database `TimestampMixin`.