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
