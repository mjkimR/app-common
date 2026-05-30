# app-layer-base Developer Guide

This guide provides expert guidance for developing FastAPI applications using the modular workspace packages. It focuses on the layered architecture, dependency injection, and hook-based customization patterns defined in `app-layer-base`.

## Core Philosophy & Architecture

The workspace promotes a clean, layered architecture to build scalable and maintainable FastAPI applications. The key layers are:

1.  **API/Router (`api/`)**: Handles HTTP requests, dependency injection, and calls UseCases.
2.  **UseCase (`usecases/`)**: Orchestrates business logic, manages database transactions, and calls Services. Inherits from `Base...UseCase` classes.
3.  **Service (`services/`)**: Implements the core business logic for a resource. Built with a mixin-based approach for CRUD operations and customized with hooks.
4.  **Repository (`repos/`)**: Provides a generic data access layer for a specific SQLAlchemy model. Inherits from `BaseRepository`.
5.  **Model (`models/`) & Schema (`schemas/`)**: Defines the database structure (SQLAlchemy) and data transfer objects (Pydantic).

## Primary Workflow: Creating a New CRUD Endpoint

Follow these steps to create a new, complete CRUD endpoint for a resource (e.g., `Book`).

### 1. Define Model and Schemas

-   **Model (`models/book.py`)**: Create the SQLAlchemy model. Use mixins from `app_layer_base.base.models.mixin` for common fields like `id`, `created_at`, etc.

    ```python
    from app_layer_base.base.models.mixin import Base, UUIDMixin, TimestampMixin
    from sqlalchemy.orm import Mapped, mapped_column

    class Book(Base, UUIDMixin, TimestampMixin):
        __tablename__ = "books"
        title: Mapped[str] = mapped_column(index=True)
        author: Mapped[str]
    ```

-   **Schemas (`schemas/book.py`)**: Define Pydantic schemas for `Create`, `Update`, and `Read`.

    ```python
    from pydantic import BaseModel
    from app_layer_base.base.schemas.mixin import UUIDSchemaMixin, TimestampSchemaMixin

    class BookBase(BaseModel):
        title: str
        author: str

    class BookCreate(BookBase):
        pass

    class BookUpdate(BaseModel):
        title: str | None = None
        author: str | None = None

    class BookRead(BookBase, UUIDSchemaMixin, TimestampSchemaMixin):
        class Config:
            from_attributes = True
    ```

### 2. Create Repository

-   **Repository (`repos/book.py`)**: Create a repository class that inherits from `BaseRepository` and links it to your model and schemas.

    ```python
    from app_layer_base.base.repos.base import BaseRepository
    from app.models.book import Book
    from app.schemas.book import BookCreate, BookUpdate

    class BookRepository(BaseRepository[Book, BookCreate, BookUpdate]):
        model = Book
    ```

### 3. Create Service & Apply Hooks

-   **Service (`services/book.py`)**: This is where you compose CRUD functionality and add business logic using hooks. Inherit from the base service mixins and any desired hook mixins.

    ```python
    from app.repos.book import BookRepository
    from app_layer_base.base.services.base import (
        BaseCreateServiceMixin,
        BaseUpdateServiceMixin,
        BaseDeleteServiceMixin,
        BaseGetServiceMixin,
        BaseGetMultiServiceMixin,
    )
    # Import desired hooks
    from app_layer_base.base.services.exists_check_hook import ExistsCheckHooksMixin
    from app_layer_base.base.services.user_aware_hook import UserAwareHooksMixin, UserContextKwargs

    class BookService(
        BaseCreateServiceMixin,
        BaseUpdateServiceMixin,
        BaseDeleteServiceMixin,
        BaseGetServiceMixin,
        BaseGetMultiServiceMixin,
        ExistsCheckHooksMixin, # Ensures book exists on update/delete
        UserAwareHooksMixin,  # Adds created_by/updated_by fields
    ):
        repo = BookRepository()
        context_model = UserContextKwargs # Specify context requirements
    ```

### 4. Create UseCases

-   **UseCases (`usecases/book.py`)**: Wrap each service operation in a UseCase. This handles transactions and decouples the API layer from the service layer.

    ```python
    from app_layer_base.base.usecases.crud import (
        BaseCreateUseCase,
        BaseGetUseCase,
        # ... import other use case bases
    )
    from app.services.book import BookService

    service = BookService()

    class CreateBookUseCase(BaseCreateUseCase):
        def __init__(self):
            super().__init__(service=service)

    class GetBookUseCase(BaseGetUseCase):
        def __init__(self):
            super().__init__(service=service)

    # ... define other use cases (Update, Delete, GetMulti)
    ```

### 5. Create API Router

-   **Router (`api/v1/books.py`)**: Create the FastAPI router. Inject the UseCases and define the endpoints.

    ```python
    from fastapi import APIRouter, Depends
    from app.usecases.book import CreateBookUseCase
    # ... import other use cases

    router = APIRouter()

    @router.post("/")
    async def create_book(
        # DI for use case, schemas, and context
    ):
        # return await CreateBookUseCase().execute(...)
        pass

    # ... define other endpoints
    ```

## Using Service Hooks

Hooks are the primary way to add business logic. Simply add the mixin to your service class.

-   **`UserAwareHooksMixin`**: Automatically adds `created_by` and `updated_by` user IDs. Requires `user_id: UUID` to be in the `context`.
-   **`ExistsCheckHooksMixin`**: Raises a `NotFoundException` if an object doesn't exist before an update or delete operation.
-   **`NestedResourceHooksMixin`**: For parent-child relationships.
    -   You must implement the `parent_repo` property.
    -   It automatically filters children by `parent_id` provided in the context.
    -   It ensures a child belongs to the correct parent on get/update/delete.
-   **`UniqueConstraintHooksMixin`**: Check for uniqueness before creating/updating. Implement the `_unique_constraints` async generator.
    ```python
    from sqlalchemy import and_

    class MyService(UniqueConstraintHooksMixin, ...):
        async def _unique_constraints(self, obj_data, context):
            if obj_data.name:
                yield (
                    and_(
                        self.repo.model.name == obj_data.name,
                        self.repo.model.parent_id == context["parent_id"]
                    ),
                    "Name must be unique within the parent."
                )
    ```

## Available Resources

When performing tasks, refer to these key files to understand the underlying patterns and base implementations.

-   `README.md`: High-level overview of the workspace.
-   `app-layer-base/src/app_layer_base/base/repos/base.py`: The `BaseRepository` implementation.
-   `app-layer-base/src/app_layer_base/base/services/base.py`: Defines all base service mixins and their hook interfaces (`_context_*`, `_prepare_*`, `_post_*`).
-   `app-layer-base/src/app_layer_base/base/services/*_hook.py`: Implementations for all standard service hooks. Review these to see how to add custom logic.
-   `app-layer-base/src/app_layer_base/base/usecases/crud.py`: The base UseCase implementations that manage transactions.
-   `app-ai-catalog/src/app_ai_catalog/models/factory.py`: The `AIModelFactory` for creating LLM and embedding models.
-   `app-layer-base/src/app_layer_base/config_util.py`: Settings loader and `ConfigLoader` utility.
-   `app-file-storage/`, `app-nosql-db/`, `app-vector-store/`, `app-event-broker/`, `app-http-client/`: Standalone adapter packages.