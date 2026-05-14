# app-base Developer Guide

This document provides a comprehensive guide to the `app-base` package. This module is the foundation for FastAPI-based applications, establishing a standardized layered architecture (Service, Repository, UseCase), model mixins, and common adapters for external systems (Storage, Vector Databases, and AI Models).

This documentation is designed to serve both developers and AI assistants as a reference for understanding and utilizing the `app-base` features effectively.

---

## Architecture & Design Patterns

The `app-base` library implements a clean, layered architecture consisting of Repositories, Services, and UseCases.

### 1. BaseRepository

The `BaseRepository` class (`app_base.base.repos.base`) acts as the standard data access layer. It abstractly handles standard CRUD operations (Create, Read, Update, Delete) and pagination.

**Key Features:**
- **Generic Typing:** Uses Python's generic types for Models and Schemas (`CreateSchemaType`, `PutSchemaType`, `PatchSchemaType`).
- **Soft Delete:** Built-in support for soft deletes. You can define the `is_deleted_column` and `deleted_at_column` (defaults are `is_deleted` and `deleted_at`).
- **Standard Methods:** Provides methods like `get`, `create`, `update`, `delete`, and querying methods like pagination handling.

### 2. BaseServiceMixinInterface & Hooks

The Service layer encapsulates business logic. `BaseServiceMixinInterface` (`app_base.base.services.base`) relies on dependency injection.

**Key Concepts:**
- **`repo` Property:** Every service implementation must provide a repository instance via the `repo` property.
- **`context_model`:** Allows defining expected context arguments using Pydantic models, which are validated dynamically.
- **Hooks (`BaseHooksInterface`):** Provides a mechanism to inject custom logic during the service execution lifecycle. Hooks such as `before_create`, `after_create`, `before_update` can be implemented to handle side-effects, validations, or events cleanly without cluttering the main service flow.

### 3. BaseUseCase

The `BaseUseCase` (`app_base.base.usecases.base`) represents a single unit of business logic. It has an abstract `execute` method that all subclass use cases must implement. This promotes the Single Responsibility Principle (SRP).

---

## Model Mixins

To enforce database schema consistency, `app-base` provides standard SQLAlchemy declarative mixins in `app_base.base.models.mixin`:

- **`UUIDMixin`**: Automatically adds an `id` column using `uuid4` as the primary key.
- **`TimestampMixin`**: Adds `created_at` and `updated_at` timestamps.
- **`AuditMixin`**: Adds `created_by` and `updated_by` fields for tracking modifications.
- **`SoftDeleteMixin`**: Adds `is_deleted` (Boolean) and `deleted_at` (DateTime) columns, along with a `mark_deleted()` helper function.
- **`TaggableMixin`**: Adds a JSON column `tags` and an `add_tag(tag: str)` helper method.

**Example Usage:**
```python
from app_base.base.models.mixin import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin

class MyModel(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "my_table"
    name: Mapped[str] = mapped_column(String)
```

---

## Adapters

Adapters provide unified interfaces for interacting with external services and storage.

### File Storage
The `FileStorageClient` (`app_base.adapter.file_storage.interface`) defines an abstraction for downloading and uploading files, as well as streaming them. Implementations (e.g., Local Storage, AWS S3) must conform to this interface. It provides methods like:
- `download_file(file_path: str) -> bytes`
- `download_file_stream(file_path: str) -> AsyncIterator[bytes]`
- `upload_file(file_path: str, data: bytes) -> None`

### Vector Store
The `VectorStoreProvider` (`app_base.adapter.vector_store.interface`) acts as a factory for creating LangChain `VectorStore` instances dynamically. It wraps operations around vector databases like Qdrant, providing:
- `create_vector_store(collection_name: str, model_name: str) -> VectorStore`

---

## AI Models (LLM & Embeddings)

`app-base` simplifies the integration of AI models using LangChain.

### LLM Factory
The `LLMFactory` (`app_base.ai.models.factory_llm`) dynamically creates LangChain `BaseChatModel` instances based on configuration (`AIModelItem`). It supports mapping specific provider arguments (like `openai-compatible`, `openai`, `google`) and initializing the correct client (`ChatOpenAI`, `ChatGoogleGenerativeAI`).

### Embedding Factory
Similarly, the `EmbeddingFactory` dynamically instantiates LangChain embedding models (e.g., OpenAI embeddings, HuggingFace embeddings) based on configuration schemas, centralizing the model initialization process.

---

## Conclusion

By standardizing database patterns (Mixins, Repository), decoupling business logic (Services, Hooks, UseCases), and abstracting external dependencies (Adapters, AI Factories), `app-base` ensures that the development of new FastAPI applications remains scalable, consistent, and easy to maintain.
