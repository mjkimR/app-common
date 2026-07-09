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

**You rarely hand-write this.** Run the code generator and it scaffolds every layer below for you:

```bash
uv run app-tools create-code feature --name Book
```

The snippets in this section are exactly what the generator emits (into `app/books/`) so you know what you get and where to customize it. The base classes are all generic and parameterized — the type parameters wire your model and schemas into the CRUD machinery, and `pyright` enforces that they line up.

### 1. Model and Schemas

-   **Model (`models.py`)**: A SQLAlchemy model using mixins from `app_layer_base.base.models.mixin` for common fields (`id`, `created_at`, ...). The generator scaffolds a single `name` column — add your own columns here.

    ```python
    from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
    from sqlalchemy.orm import Mapped, mapped_column

    class Book(Base, UUIDMixin, TimestampMixin):
        __tablename__ = "books"
        name: Mapped[str] = mapped_column()
    ```

-   **Schemas (`schemas.py`)**: Pydantic DTOs split by operation. `Create` and `Put` (full replace) carry required fields; `Patch` (partial update) makes every field optional; `Read` maps from the ORM object via `ConfigDict(from_attributes=True)`.

    ```python
    from pydantic import BaseModel, ConfigDict, Field

    from app_layer_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin

    class BookBase(BaseModel):
        name: str = Field(description="The name of the book.")

    class BookCreate(BookBase):
        pass

    class BookPut(BookBase):
        pass

    class BookPatch(BaseModel):
        name: str | None = Field(default=None, description="The name of the book.")

    class BookRead(UUIDSchemaMixin, TimestampSchemaMixin, BookBase):
        model_config = ConfigDict(from_attributes=True)
    ```

### 2. Repository

-   **Repository (`repos.py`)**: Inherits from `BaseRepository[Model, Create, Put, Patch]` and binds it to your model. This gives you `get`, `create`, `update`, `delete`, `exists`, and paginated list queries for free.

    ```python
    from app_layer_base.base.repos.base import BaseRepository
    from app.books.models import Book
    from app.books.schemas import BookCreate, BookPut, BookPatch

    class BookRepository(BaseRepository[Book, BookCreate, BookPut, BookPatch]):
        model = Book
    ```

### 3. Service & Context

-   **Service (`services.py`)**: Composes the CRUD mixins and is where you add business logic via hooks. Each mixin is parameterized with the repository, model, the schemas it needs, and a **context** type (a `TypedDict` carrying request-scoped data like `user_id`). The repository is injected via FastAPI `Depends`.

    ```python
    from typing import Annotated

    from fastapi import Depends

    from app_layer_base.base.services.base import (
        BaseContextKwargs,
        BaseCreateServiceMixin,
        BaseDeleteServiceMixin,
        BaseGetMultiServiceMixin,
        BaseGetServiceMixin,
        BaseUpdateServiceMixin,
    )
    from app.books.models import Book
    from app.books.repos import BookRepository
    from app.books.schemas import BookCreate, BookPut, BookPatch

    class BookContextKwargs(BaseContextKwargs):
        pass

    class BookService(
        BaseCreateServiceMixin[BookRepository, Book, BookCreate, BookContextKwargs],
        BaseGetMultiServiceMixin[BookRepository, Book, BookContextKwargs],
        BaseGetServiceMixin[BookRepository, Book, BookContextKwargs],
        BaseUpdateServiceMixin[BookRepository, Book, BookPut, BookPatch, BookContextKwargs],
        BaseDeleteServiceMixin[BookRepository, Book, BookContextKwargs],
    ):
        def __init__(self, repo: Annotated[BookRepository, Depends()]):
            self._repo = repo

        @property
        def repo(self) -> BookRepository:
            return self._repo

        @property
        def context_model(self):
            return BookContextKwargs
    ```

    To add business logic, mix in a hook (see [Using Service Hooks](#using-service-hooks)) — e.g. add `UniqueConstraintHooksMixin` and switch `context_model` to `UserContextKwargs` when you need the acting user.

### 4. UseCases

-   **UseCases (`usecases/crud.py`)**: One class per operation. Each wraps the service, manages the transaction, and is itself injectable. Note there is **no single "Update"** use case — `Put` (full replace) and `Patch` (partial) are separate.

    ```python
    from typing import Annotated

    from fastapi import Depends

    from app_layer_base.base.usecases.crud import (
        BaseCreateUseCase,
        BaseDeleteUseCase,
        BaseGetMultiUseCase,
        BaseGetUseCase,
        BasePatchUseCase,
        BasePutUseCase,
    )
    from app.books.models import Book
    from app.books.schemas import BookCreate, BookPut, BookPatch
    from app.books.services import BookService, BookContextKwargs

    class CreateBookUseCase(BaseCreateUseCase[BookService, Book, BookCreate, BookContextKwargs]):
        def __init__(self, service: Annotated[BookService, Depends()]) -> None:
            super().__init__(service)

    class PatchBookUseCase(BasePatchUseCase[BookService, Book, BookPut, BookPatch, BookContextKwargs]):
        def __init__(self, service: Annotated[BookService, Depends()]) -> None:
            super().__init__(service)

    # ... Get, GetMulti, Put, Delete follow the same pattern
    ```

### 5. API Router

-   **Router (`api/v1.py`)**: Declares the endpoints. UseCases, path params, and request bodies are all resolved through `Annotated[..., Depends()]` / FastAPI parameter injection. The generator wires 6 routes: create, list, get, patch, put, delete.

    ```python
    from typing import Annotated

    from fastapi import APIRouter, Depends, status

    from app_layer_base.base.schemas.paginated import PaginatedList
    from app.books.schemas import BookCreate, BookRead
    from app.books.usecases.crud import CreateBookUseCase, GetMultiBookUseCase

    router = APIRouter(prefix="/books", tags=["Book"], dependencies=[])

    @router.post("", status_code=status.HTTP_201_CREATED, response_model=BookRead)
    async def create_book(
        use_case: Annotated[CreateBookUseCase, Depends()],
        book_in: BookCreate,
    ):
        return await use_case.execute(book_in)

    @router.get("", response_model=PaginatedList[BookRead])
    async def get_books(
        use_case: Annotated[GetMultiBookUseCase, Depends()],
        # pagination + query options omitted for brevity
    ):
        ...
    ```

    `api/__init__.py` re-exports the router as `v1_books_router`; register it on your FastAPI app (or via `app-tools update-router`).

## Using Service Hooks

Hooks are the primary way to add business logic. Add the mixin to your service class and implement its extension point. All hooks are generic and take the same context type as the service.

-   **`UserAwareHooksMixin`**: Automatically stamps `created_by` / `updated_by`. Requires `user_id: UUID` in the context (use `UserContextKwargs`).
-   **`ExistsCheckHooksMixin`**: Raises `NotFoundException` if the object doesn't exist before an update or delete.
-   **`NestedResourceHooksMixin`**: For parent-child relationships.
    -   Implement the `parent_repo` property.
    -   Automatically filters children by `parent_id` from the context (`NestedResourceContextKwargs`) and enforces that a child belongs to the correct parent on get/update/delete.
-   **`UniqueConstraintHooksMixin`**: Check uniqueness before create/update. Implement the `_unique_constraints` async generator; raises `ConflictException` on a match.
    ```python
    from sqlalchemy import and_

    class MyService(UniqueConstraintHooksMixin, ...):
        async def _unique_constraints(self, obj_data, context):
            if obj_data.name:
                yield (
                    and_(
                        self.repo.model.name == obj_data.name,
                        self.repo.model.parent_id == context["parent_id"],
                    ),
                    "Name must be unique within the parent.",
                )
    ```
-   **`DomainEventHooksMixin`**: Publishes domain events (e.g. `Book.created`) after CUD operations. Implement the abstract `publish_event(topic, payload)` to wire it to your transport of choice — it is transport-agnostic and has no message-broker dependency.
-   **`DetailDeleteResponseHookMixin`**: Enriches the delete response with detail about the removed object(s).

## Available Resources

When performing tasks, refer to these key files to understand the underlying patterns and base implementations.

-   `README.md`: High-level overview of the workspace.
-   `app-layer-base/src/app_layer_base/base/repos/base.py`: The `BaseRepository` implementation.
-   `app-layer-base/src/app_layer_base/base/services/base.py`: Defines all base service mixins and their hook interfaces (`_context_*`, `_prepare_*`, `_post_*`).
-   `app-layer-base/src/app_layer_base/base/services/*_hook.py`: Implementations for all standard service hooks. Review these to see how to add custom logic.
-   `app-layer-base/src/app_layer_base/base/usecases/crud.py`: The base UseCase implementations that manage transactions.
-   `app-ai-catalog/src/app_ai_catalog/models/factory.py`: The `AIModelFactory` for creating LLM and embedding models.
-   `app-layer-base/src/app_layer_base/config_util.py`: Settings loader and `ConfigLoader` utility.
-   `app-file-storage/`, `app-vector-store/`, `app-http-client/`: Standalone adapter packages (see each package's README).
