# Sessions and transaction ownership

Read when changing DB session acquisition or transactions in an app-layer-base application.
For installation and database configuration, see [setup](setup.md); for test fixtures,
see [testing](../testing/index.md). HTTP-only or timestamp-only work does not need these.

```python
from typing import Annotated
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app_layer_base.core.database.deps import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
```

`get_session` yields and closes a session; it does not commit automatically. UseCase
owns the transaction boundary and passes the session to services/repositories. Service
hooks perform business work without committing or rolling back. Reuse the configured
engine/session maker; a deliberately separate database needs its own explicit lifecycle.

`ARCH_DB_FACTORY_IN_LAYER` warns about engine/session-factory creation in routers or
services. `ARCH_SERVICE_COMMIT` catches service commit/rollback calls. It is a convention-based
check, not proof of transaction correctness. Read [backend](index.md) for broader layer
changes and [hooks](hooks.md) only when implementing hooks.

## Stores that own their engine and transaction

Use [TransactionScope and command execution](commands.md) to standardize the context
above a domain store, including nesting, write-policy checks and cache cleanup.

A non-CRUD application can supply its own session maker:

```python
from app_layer_base.core.database.transaction import AsyncTransaction

async with AsyncTransaction(session_maker=store.maker) as session:
    await update_project(session)
```

The owning boundary commits on success, rolls back on a body exception, and closes
the session. `AsyncTransaction(session=session)` joins an existing session and leaves
commit, rollback, close, and after-commit dispatch to the owner. Domain-specific locks
and repository bundles remain application responsibilities. Avoid opening a new
transaction inside a command whose caller already owns one.

Importing the transaction utility does not configure the global logger or read
application settings. The default maker still loads settings when actually requested;
an explicit maker avoids it. Logger setup belongs to application startup. After-commit
callbacks remain best-effort and are dispatched only by the owning shared transaction.
