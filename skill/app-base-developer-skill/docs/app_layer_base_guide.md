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
            # Ordered hooks for this service; see "Using Service Hooks" below.
            # e.g. self.hooks = (ExistsCheckHook(), NestedResourceHook(parent_repo))
            self.hooks = ()

        @property
        def repo(self) -> BookRepository:
            return self._repo

        @property
        def context_model(self):
            return BookContextKwargs
    ```

    To add business logic, declare hooks (see [Using Service Hooks](#using-service-hooks)) — e.g. add a `UniqueConstraintHook` subclass to `hooks`, and switch `context_model` to `UserContextKwargs` when you need the acting user.

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

Hooks are the primary way to add business logic. A hook is a **standalone object**, not a mixin on the service: your service declares one ordered `hooks` tuple, and the service executor runs it.

```python
class ChapterService(
    BaseCreateServiceMixin[ChapterRepository, Chapter, ChapterCreate, NestedResourceContextKwargs],
    BaseDeleteServiceMixin[ChapterRepository, Chapter, NestedResourceContextKwargs],
):
    def __init__(
        self,
        repo: Annotated[ChapterRepository, Depends()],
        book_repo: Annotated[BookRepository, Depends()],
        outbox_repo: Annotated[OutboxRepository, Depends()],
    ):
        self._repo = repo
        self.hooks = (
            ChapterUniqueHook(),
            NestedResourceHook(book_repo, fk_name="book_id"),
            ExistsCheckHook(),
            ChapterOutboxHook(outbox_repo, CHAPTER_EVENTS),
        )

    @property
    def repo(self) -> ChapterRepository:
        return self._repo

    @property
    def context_model(self):
        return NestedResourceContextKwargs
```

Hooks with no dependencies can just as well be declared as a class attribute (`hooks = (ExistsCheckHook(),)`); ones that need a repository or a client take it as a constructor argument, so build the tuple in `__init__`.

### The contract

-   **Declaration order is execution order.** For each operation the executor selects the hooks implementing that operation's protocol, enters every hook's context in declaration order, runs the repository call, then unwinds in reverse — so `*_post` methods run in **reverse** declaration order, mirroring context exit.
-   **A hook never calls `super()` and never calls the next hook.** The executor owns the chain, so a hook implements only its own behaviour and cannot break the chain for the hooks after it. Adding, reordering, or removing a hook cannot silently disable another one.
-   **Every hook method takes an `Operation` first**: `op.session`, `op.context`, `op.repo`, and `op.state` — a scratch dict scoped to a single service call.
-   **Carry per-call state on `op.state`, never on the hook instance.** Hooks are shared across items and across calls, so a value stashed on `self` in a context hook leaks into the next item and the next request. Put it on `op.state` (keyed by pk when the operation is bulk) and read it back in the matching `*_post` hook.
-   **Context keys are a checked contract.** `BaseContextKwargs` forbids undeclared keys (`extra="forbid"`, inherited by every subclass), so passing a key the `context_model` does not declare raises instead of being silently dropped. A hook that reads context keys declares them via `required_context_keys = frozenset({...})`; the executor raises `TypeError` on the first operation when the service's `context_model` is missing one — declare the key on the model as `Required` (callers must pass it) or `NotRequired` (the hook tolerates absence).

### Hook protocols

Implement only the operations your hook cares about; the executor ignores the rest.

| Protocol | Methods |
|---|---|
| `CreateHook` | `create_context`, `create_prepare_fields`, `create_post`, `create_context_multi`, `create_post_multi` |
| `UpdateHook` | `update_context`, `update_prepare_fields`, `update_post` |
| `DeleteHook` | `delete_context`, `delete_post`, `delete_context_multi`, `delete_post_multi` |
| `GetHook` | `get_context`, `get_post` |
| `GetMultiHook` | `get_multi_context`, `get_multi_prepare_filters`, `get_multi_post` |

`*_context` methods are async context managers: validate before the `yield`, clean up (or emit) after it. `*_prepare_fields` rewrites the column values handed to the repository. `*_post` sees the result.

### Bulk methods, and why they are per-hook

The `*_multi` methods let a hook replace **its own** per-item behaviour with a single bulk query — `NestedResourceHook` checks the parent once instead of once per item; `ExistsCheckHook` uses one `IN` query; `DomainEventHook` publishes one aggregate `Book.created_multi` event instead of N.

Overriding a bulk method affects **only the hook that overrides it**. The executor asks each hook separately, and any hook that has not overridden the bulk method still gets its single-item hook applied to every item. This is the whole point of the design: in the previous MRO-chained version, one hook defining a bulk method silently switched off *every other hook's* per-item hooks — which lost outbox events and skipped unique-constraint checks on `create_multi`. See `app-layer-base/tests/unit/test_layer_base/test_services/test_hook_combinations.py`, which pins that invariant.

### Pre-built hooks

-   **`UserAwareHook`**: Stamps `created_by` / `updated_by`. Requires `user_id: UUID` in the context (use `UserContextKwargs`). Stateless, no deps.
-   **`ExistsCheckHook`**: Raises `NotFoundException` if the object doesn't exist before an update or delete. Stateless, no deps.
-   **`NestedResourceHook(parent_repo, fk_name="parent_id")`**: For parent-child relationships. Injects the foreign key on create, filters lists by `parent_id` from the context (`NestedResourceContextKwargs`), and enforces that a child belongs to the correct parent on get/update/delete. `fk_name` also accepts a sequence of names for a composite key.
-   **`UniqueConstraintHook`**: Checks uniqueness before create/update. Implement the `constraints` async generator; a matching row raises `ConflictException` (HTTP 409).
    ```python
    from sqlalchemy import and_

    class ChapterUniqueHook(UniqueConstraintHook[Chapter, NestedResourceContextKwargs]):
        async def constraints(self, op, data):
            if data.name:
                yield (
                    and_(
                        op.repo.model.name == data.name,
                        op.repo.model.book_id == op.context["parent_id"],
                    ),
                    "Name must be unique within the parent.",
                )
    ```
-   **`DomainEventHook`**: Publishes domain events (e.g. `Book.created`) after CUD operations. Implement the abstract `publish_event(topic, payload)` to wire it to your transport of choice — it is transport-agnostic and has no message-broker dependency. Override `payload(op, event_type, pk, obj=None)` to put more than the resource id in the event body. **Publishing is deferred until the transaction commits** (via `op.register_after_commit`): the payload is captured while the row is in hand, but `publish_event` fires only once the write is durable, so a rolled-back write never emits an event. This is **at-most-once, best-effort** — a failed publish is logged and lost. When the event must not be lost, use `OutboxHook` (writes it in the same transaction) instead.
-   **`DetailDeleteResponseHook`**: Puts a human-readable representation of the deleted row on `DeleteResponse.representation`. Implement `represent(obj) -> str`; the row is read before the delete and the text is stashed on `op.state`, keyed by pk. It sits `delete_multi` out entirely -- `MultipleDeleteResponse` has nowhere to put a per-item representation, so reading every row would be N queries for output nobody can see.

`app-prebuilt-outbox` ships one more: **`OutboxHook(outbox_repo, event_types)`**, which writes an outbox row in the same transaction as the change. Implement `payload(op, obj, identity)`. See its [README](../../../app-prebuilt-outbox/README.md).

## Where Logic Lives — Layering Rules

The hook system only pays off if logic stays where the executor can run it. These rules keep it that way; each exists because the opposite pattern has already caused real problems in consuming apps (hook bypasses and split transactions).

### 1. A use case is a transaction boundary plus orchestration — nothing else

`Base*UseCase.execute()` opens one `AsyncTransaction`, calls services, and returns. The `_execute` / `_post_execute` / `_context_execute` overrides are seams for *orchestration concerns of that one scenario* (ordering calls, side effects like a cache refresh). They are **not** a home for business rules.

Litmus test: if the rule must hold no matter which code path touches the resource ("only one default model", "children belong to their parent", "names are unique"), it is an invariant and belongs in a **service hook**. A rule implemented in a use case override silently disappears the moment another use case, worker, or composition path writes the same resource.

### 2. Never call a use case from a use case

Each `execute()` opens its own `AsyncTransaction` by default. Nesting one inside another *without sharing the session* does not create a nested transaction — it creates a **second, independent session on a separate connection**: the inner one commits even if the outer rolls back, cannot see the outer session's uncommitted changes, and can deadlock against the outer session's row locks. So compose at the service layer (rule 3), not by calling one use case from another.

There is a deliberate **escape hatch** for the rare case where reusing a use case as-is beats refactoring it right now: `execute(..., session=existing)` makes it *join* your transaction instead of opening its own (internally `AsyncTransaction(session=existing)` becomes a pass-through — the caller owns the commit, rollback, close, and after-commit dispatch). Treat it as a bridge, not a pattern: prefer service-layer composition, and reach for `session=` only when the dependency-tangling risk is low or the refactor is imminent. A `DomainEventHook` inside a joined use case registers its publish on *your* session, so it fires only when *you* commit — if your outer boundary is not an `AsyncTransaction`, you are responsible for dispatching it (`run_after_commit(session)`).

### 3. To compose, open one transaction and call several services

Services take `session` as an argument and never commit — they are composable by construction, and hooks run inside service methods. A cross-resource operation is a **new use case** that opens a single transaction:

```python
class ArchiveDocsAndDeleteKbUseCase(BaseUseCase):
    def __init__(self, kb_service, doc_service): ...

    async def execute(self, kb_id, context=None):
        async with AsyncTransaction() as session:      # exactly one
            docs = await self.doc_service.get_multi(session, ...)
            for doc in docs.items:
                await self.doc_service.patch(
                    session, doc.id, DocPatch(status="archived"), context=context
                )
            return await self.kb_service.delete(session, kb_id, context=context)
```

Every hook still runs; one commit; a failure rolls back everything. If the same service combination recurs across use cases, promote it to a facade that takes `session` — the use case then opens the transaction and calls the facade.

### 4. Custom queries live in the repository; writes go through the service

When the base repo cannot express a query (locking reads, bulk state flips, lookups by column), add a **method on your repository subclass** — raw SQLAlchemy is at home there — and expose it through a service method. What you must not do is issue raw `session.execute(...)` from a use case, or call `service.repo.<write>` directly: both skip every hook the service declares (uniqueness, ownership, audit stamping, events/outbox).

`service.repo` exists for wiring and for hooks (`op.repo`); treat it as plumbing, not a write shortcut.

### 5. Reads may go straight to the repo — with one condition

Skipping a layer downward is not a dependency-rule violation; the problem is only ever the behavior you skip. So:

- **Writes: always through the service.** No exceptions — this is where invariants live.
- **Reads: calling `repo.get_by_pk` / `repo.get` / `repo.get_multi` from a use case is fine *if and only if* the service declares no read hooks.** The moment a `GetHook`/`GetMultiHook` appears (e.g. `NestedResourceHook` scoping lists to a parent — a security filter), every direct read becomes a scoping bypass. If in doubt, or if the service might grow read hooks later, go through `service.get` / `service.get_multi`.

## Available Resources

When performing tasks, refer to these key files to understand the underlying patterns and base implementations.

-   `README.md`: High-level overview of the workspace.
-   `app-layer-base/src/app_layer_base/base/repos/base.py`: The `BaseRepository` implementation.
-   `app-layer-base/src/app_layer_base/base/services/base.py`: The base service mixins and the executor that runs a service's `hooks` tuple.
-   `app-layer-base/src/app_layer_base/base/services/hooks.py`: The hook protocols (`*_context`, `*_prepare_*`, `*_post`, `*_multi`) and `Operation`.
-   `app-layer-base/src/app_layer_base/base/services/*_hook.py`: Implementations for all standard service hooks. Review these to see how to add custom logic.
-   `app-layer-base/src/app_layer_base/base/usecases/crud.py`: The base UseCase implementations that manage transactions.
-   `app-ai-catalog/src/app_ai_catalog/models/factory.py`: The `AIModelFactory` for creating LLM and embedding models.
-   `app-layer-base/src/app_layer_base/config_util.py`: Settings loader and `ConfigLoader` utility.
-   `app-file-storage/`, `app-vector-store/`, `app-http-client/`: Standalone adapter packages (see each package's README).
