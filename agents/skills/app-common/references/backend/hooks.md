# Service Hooks Guide (`app_layer_base.base.services.hooks`)

Business logic is encapsulated in isolated, composable **Service Hooks**.
A service declares an ordered tuple of hooks: `hooks = (HookA(), HookB())`.

## Hook Execution Order

Hooks use an async context manager pattern:
1. `__aenter__` executes in forward order: HookA enter $\rightarrow$ HookB enter.
2. Repository CRUD operation executes.
3. `__aexit__` executes in reverse order: HookB exit $\rightarrow$ HookA exit.

> **Rules**:
> - Hooks **never** call `super()`.
> - Hooks **never** call each other.
> - Hooks must not call `session.commit()` or `session.rollback()` (handled by UseCase/session).

---

## Hook Protocols

Implement one or more protocols in `app_layer_base.base.services.hooks`:

| Protocol | Methods | Triggered By |
|---|---|---|
| `CreateHook[Model, CreateSchema]` | `create_scope(session, data)` | `service.create`, `service.create_multi` |
| `UpdateHook[Model, UpdateSchema]` | `update_scope(session, id, data)` | `service.update`, `service.update_multi` |
| `DeleteHook[Model]` | `delete_scope(session, id)` | `service.delete`, `service.delete_multi` |
| `GetHook[Model]` | `get_scope(session, id)` | `service.get` |
| `GetMultiHook[Model]` | `get_multi_scope(session, params)` | `service.get_multi` |

---

## Example: Uniqueness & Validation Hook

```python
from contextlib import asynccontextmanager
from typing import AsyncIterator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app_layer_base.base.services.base import BaseService
from app_layer_base.base.services.hooks import CreateHook
from app_error import AppError, Actor, Retry


class UniqueIsbnHook(CreateHook[Book, BookCreate]):
    async def before_create(self, session: AsyncSession, data: BookCreate) -> None:
        stmt = select(Book.id).where(Book.isbn == data.isbn).limit(1)
        exists = await session.scalar(stmt)
        if exists:
            raise AppError(
                f"ISBN {data.isbn} is already registered",
                code="ISBN_ALREADY_EXISTS",
                actor=Actor.USER,
                retry=Retry.SAFE,
                fix="Please check the ISBN and try again with an unregistered number.",
            )

    @asynccontextmanager
    async def create_scope(self, session: AsyncSession, data: BookCreate) -> AsyncIterator[None]:
        # Pre-operation validation
        await self.before_create(session, data)
        yield
        # Post-operation logic (if any) can be placed here after yield


class BookService(BaseService[Book, BookCreate, BookUpdate]):
    hooks = (UniqueIsbnHook(),)
```

---

## Composing Multiple Hooks

Hooks are executed in the exact order declared:

```python
class BookService(BaseService[Book, BookCreate, BookUpdate]):
    hooks = (
        AuditLoggingHook(),
        UniqueIsbnHook(),
        OutboxHook(...),
    )
```
Entry: Audit enter $\rightarrow$ Isbn enter $\rightarrow$ Outbox enter $\rightarrow$ **Repo CRUD** $\rightarrow$ Outbox exit $\rightarrow$ Isbn exit $\rightarrow$ Audit exit.
