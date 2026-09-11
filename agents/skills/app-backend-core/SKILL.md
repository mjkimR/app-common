---
name: app-backend-core
description: FastAPI 4-layer architecture (Router, UseCase, Service Hooks, Repo), code scaffolding with app-tools, and structured error handling with app-error.
---

# app-backend-core

This skill guides development of FastAPI applications built on `app-layer-base`, `app-tools`, and `app-error`.

> For package installation commands and database configuration, see [setup.md](./setup.md).

## Quick Scaffolding

**Never hand-write boilerplate from scratch.** Use `app-tools` to scaffold a complete feature:

```bash
uv run app-tools create-code feature --name Book
# With explicit plural:
uv run app-tools create-code feature --name Category --plural categories
```

Generated structure in `app/books/`:
```
books/
├── models.py       # SQLAlchemy model with standard mixins
├── schemas.py      # Pydantic validation schemas (Create, Update, Response)
├── repo.py         # BaseRepository implementation
├── service.py      # BaseService with hooks tuple
├── usecase.py      # Transaction-aware UseCase coordinating services
├── router.py       # FastAPI router with dependency injection
└── deps.py         # Annotated dependency injection providers
```

---

## 1. Layered Architecture Flow

Requests strictly follow:
`Client -> Router -> UseCase -> Service (Hooks) -> Repository -> Database`

| Layer | Responsibility | What it MUST NOT do |
|---|---|---|
| **Router** (`router.py`) | HTTP protocol, status codes, query/body validation, route dependencies. Delegates directly to UseCase. | No direct DB queries, no direct business rules. |
| **UseCase** (`usecase.py`) | Transaction boundaries (`session.commit()`), cross-service orchestration, external adapter invocation. | No raw SQL, no HTTP request/response objects. |
| **Service** (`service.py`) | Domain business logic via `hooks = (...)` tuple. Pre/post operation constraints. | No commit/rollback calls (handled by UseCase/session). |
| **Repository** (`repo.py`) | Generic data access via SQLAlchemy ORM (`BaseRepository`). Filters, pagination, ordering. | No business validation rules. |
| **Model & Schema** (`models.py`, `schemas.py`) | Declarative DB persistence & Pydantic validation schemas. | No side effects. |

---

## 2. Models & Mixins (`app_layer_base.base.models`)

Inherit from `Base` and composition mixins:

```python
from app_layer_base.base.models.base import Base
from app_layer_base.base.models.mixin import UUIDMixin, TimestampMixin, SoftDeleteMixin
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

class Book(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "books"

    title: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    isbn: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
```

- `UUIDMixin`: Generates UUIDv7 primary key `id`.
- `TimestampMixin`: Adds `created_at` and `updated_at` (UTC).
- `SoftDeleteMixin`: Adds `is_deleted` and `deleted_at`.
  *Important*: Rows are only filtered if the repository opts in:
  ```python
  class BookRepository(BaseRepository[Book, BookCreate, BookUpdate]):
      soft_delete_enabled = True
  ```

---

## 3. Service Hooks (`app_layer_base.base.services.hooks`)

Business logic is encapsulated in isolated, composable **Service Hooks**.
A service defines an ordered tuple: `hooks = (HookA(), HookB())`.

### Hook Execution Flow
Hooks use an async context manager pattern:
1. `__aenter__` executes in forward order (HookA enter -> HookB enter).
2. Repository CRUD operation executes.
3. `__aexit__` executes in reverse order (HookB exit -> HookA exit).

Hooks **never** call `super()` and **never** call each other.

### Hook Protocols
- `CreateHook[Model, CreateSchema]`
- `UpdateHook[Model, UpdateSchema]`
- `DeleteHook[Model]`
- `GetHook[Model]`
- `GetMultiHook[Model]`

### Example: Uniqueness & Audit Hook

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from app_layer_base.base.services.base import BaseService
from app_layer_base.base.services.hooks import CreateHook
from app_error import AppError, Actor, Retry

class UniqueIsbnHook(CreateHook[Book, BookCreate]):
    async def before_create(self, session: AsyncSession, data: BookCreate) -> None:
        exists = await session.scalar(...)
        if exists:
            raise AppError(
                f"ISBN {data.isbn} already registered",
                code="ISBN_ALREADY_EXISTS",
                actor=Actor.USER,
                retry=Retry.SAFE,
                fix="Please check the ISBN and try again with an unregistered number."
            )

    @asynccontextmanager
    async def create_scope(self, session: AsyncSession, data: BookCreate) -> AsyncIterator[None]:
        await self.before_create(session, data)
        yield

class BookService(BaseService[Book, BookCreate, BookUpdate]):
    hooks = (UniqueIsbnHook(),)
```

---

## 4. UseCases & Transaction Boundaries

UseCases manage the lifecycle of changes across one or more services:

```python
from app_layer_base.base.usecases.base import BaseUseCase
from sqlalchemy.ext.asyncio import AsyncSession

class BookUseCase(BaseUseCase):
    def __init__(self, book_service: BookService, session: AsyncSession) -> None:
        self.service = book_service
        self.session = session

    async def register_book(self, data: BookCreate) -> BookResponse:
        # Atomic unit of work
        book = await self.service.create(self.session, data)
        await self.session.commit()
        await self.session.refresh(book)
        return BookResponse.model_validate(book)
```

---

## 5. Dependency Injection (`deps.py`)

Always use `Annotated[T, Depends(...)]` for FastAPI dependencies:

```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app_layer_base.core.database.deps import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]

def get_book_service() -> BookService:
    return BookService(repo=BookRepository(Book))

BookServiceDep = Annotated[BookService, Depends(get_book_service)]

def get_book_usecase(
    service: BookServiceDep,
    session: SessionDep,
) -> BookUseCase:
    return BookUseCase(book_service=service, session=session)

BookUseCaseDep = Annotated[BookUseCase, Depends(get_book_usecase)]
```

---

## 6. Structured Errors & Agent Advisory (`app-error`)

Raise structured `AppError` exceptions rather than generic `ValueError` or raw `HTTPException`.
This provides clear guidance for both humans and AI agents.

```python
from app_error import AppError, Actor, Retry, ActionMode

class ResourceNotFoundError(AppError):
    code = "RESOURCE_NOT_FOUND"
    actor = Actor.USER
    retry = Retry.UNSAFE

raise ResourceNotFoundError(
    "Book with id 42 does not exist",
    code="BOOK_NOT_FOUND",
    actor=Actor.USER,
    retry=Retry.UNSAFE,
    fix="Verify the book ID from the listing endpoint.",
    what_to_report="The requested book ID does not exist in the database.",
)
```

### Advisory Fields
- `actor`: `Actor.USER` (user must fix input), `Actor.AGENT` (agent can auto-correct), `Actor.DEV` (needs code fix).
- `retry`: `Retry.SAFE` (idempotent retry), `Retry.UNSAFE` (do not blindly retry).
- `fix`: Clear, actionable string instruction for how to resolve the issue.
- `what_to_report`: Summarized explanation suitable for user-facing responses.
- `render_mcp()` / `lines()`: Renderers for tool response contexts or CLI output.
