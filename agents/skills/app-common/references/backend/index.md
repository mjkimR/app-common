# app-backend-core

FastAPI layered architecture framework based on `app-layer-base`, `app-tools`, and `app-error`.

> **References**:
> - Package Installation & Database Configuration: [setup.md](./setup.md)
> - Service Hooks (Custom Business Logic & Scopes): [hooks.md](./hooks.md)
> - Structured Errors & Agent Advisory: [errors.md](./errors.md)

---

## Architecture checks

Run `app-tools check-arch <source-directory> --json` for actionable architecture
violations with rule codes, locations, and fixes. To include it in `app-tools run lint`,
set `[tool.app-tools] check-arch = true` in pyproject.toml. The checks below cover
router repository imports (`ARCH_ROUTER_REPO_IMPORT`), service transactions
(`ARCH_SERVICE_COMMIT`), and hook chaining (`ARCH_HOOK_SUPER_CALL`). A justified
exception uses `# arch: ignore[ARCH_SERVICE_COMMIT] -- reason` on the reported line.
Checks use source conventions; the explanations below still guide design decisions.

## Non-CRUD consumers

For a consistent feature shape, caller-owned execution, and checks that keep agent-written
features aligned, use [command features](commands.md). This is the supported non-CRUD
path alongside the CRUD stack below.

Use shared infrastructure without adopting generated CRUD features. A verb-driven
application may use ordinary constructors, domain-specific repositories, and one
caller-owned transaction. Keep its transport handlers thin and its domain logic
independent of FastAPI. The Service Hooks and scaffolding rules below apply to
features built on the CRUD service stack, not to all consumers of app-common.
HTTP-only tests can use [testing](../testing/index.md) without the default DB fixtures.

Declare application-specific import boundaries in the nearest pyproject.toml:

```toml
[[tool.app-tools.architecture.boundaries]]
name = "domain is independent of transport"
source = "my_app.features"
forbidden_imports = ["my_app.server", "fastapi", "sqlalchemy"]
```

Each boundary requires a unique nonempty `name`, a dotted module `source`, and a
nonempty `forbidden_imports` list. Names match exactly or at a module-component
boundary (`my_app.server` includes its children, but not `my_app.server_utils`).
The scanner supports `src/` and flat layouts, absolute and relative imports,
including `from package import module`. Nested projects use their own configuration;
it is not inherited across a Git boundary. These are static import checks, including
imports inside functions and type-checking branches, not runtime dependency tracing.
Tests and migrations retain the existing scanner exclusions.

`ARCH_FORBIDDEN_IMPORT` is an error; a deliberate exception uses the existing
inline `# arch: ignore[ARCH_FORBIDDEN_IMPORT] -- reason` syntax. Invalid configuration
fails with `ARCH_CONFIG_ERROR`. Existing CRUD checks continue to run unchanged.
Run `app-tools check-arch src --json` and wire it into the consumer's normal checks.

## Critical Invariants (CRUD service stack)

| Forbidden Action | Why It Breaks The System | Correct Pattern |
|---|---|---|
| **Calling `super()` in Hook methods** | Hooks are isolated protocols chained by executor; calling `super()` causes duplicate or broken hook runs. | Implement method standalone (`create_pre`, etc.). |
| **Router directly importing `repos`** | Violates 4-layer architecture and bypasses UseCase transaction & Service Hooks. | Router delegates to `UseCase` or `Service`. |
| **Calling `commit()` inside Service** | Services contain business logic, not transaction boundaries. | Transactions are committed by `UseCase` or session lifespan. |
| **Random data generators** | Generates non-deterministic strings that fail unique/format constraints. | Use `app_testing_base.random_string` & explicit `make_*_payload`. |

---

## Quick Scaffolding

**Never hand-write boilerplate from scratch.** Use `app-tools` to scaffold a complete feature:

```bash
uv run app-tools create-code feature --name Book
# Preview without touching disk:
uv run app-tools create-code feature --name Book --dry-run --json
# With explicit plural:
uv run app-tools create-code feature --name Category --plural categories
```

Generated structure in `app/features/books/`:
```
books/
├── models.py       # SQLAlchemy model with standard mixins
├── schemas.py      # Pydantic validation schemas (Create, Update, Response)
├── repos.py        # BaseRepository implementation
├── services.py     # BaseService with hooks tuple
├── usecases/       # Transaction-aware UseCases coordinating services
│   ├── __init__.py
│   └── crud.py
├── api/            # FastAPI router with dependency injection
│   ├── __init__.py
│   └── v1.py
└── tests/          # Integration tests inheriting from IntegrationTest
    ├── __init__.py
    └── test_integrate.py
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
  *Note*: Rows are filtered only when the repository opts in:
  ```python
  class BookRepository(BaseRepository[Book, BookCreate, BookUpdate]):
      soft_delete_enabled = True
  ```

---

## 3. Service Hooks (`app_layer_base.base.services.hooks`)

Business logic is encapsulated in isolated, composable **Service Hooks**.
A service declares an ordered tuple: `hooks = (HookA(), HookB())`.

- Hooks execute via async context managers: Forward enter $\rightarrow$ Repo CRUD $\rightarrow$ Reverse exit.
- Hooks **never** call `super()` and **never** call each other.
- For complete hook protocols (`CreateHook`, `UpdateHook`, etc.) and implementation examples, see **[hooks.md](./hooks.md)**.

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

## 6. Structured Error Handling (`app-error`)

Raise structured `AppError` subclasses with `Actor` and `Retry` advisories rather than generic `ValueError` or raw `HTTPException`.
For advisory fields (`Actor`, `Retry`, `ActionMode`), remediation properties (`fix`, `what_to_report`), and MCP/CLI renderers, see **[errors.md](./errors.md)**.

---

## 7. Modifying `app-common` Packages Locally (`app-local-dev`)

To modify `app-common` packages while working in a consumer project without modifying `pyproject.toml` or `package.json`, see the **[local development](../local-dev/index.md)** skill (`uv run app-tools dev link / unlink / status`).
