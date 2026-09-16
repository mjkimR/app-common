# app-prebuilt-outbox

Guaranteed message delivery: domain events are saved in the same database transaction as business writes, then a background relay publishes them with `SELECT ... FOR UPDATE SKIP LOCKED` guarantees.

> For package installation and database requirements, see [setup.md](./setup.md).

## Step 1: Emit Events via `OutboxHook`

Subclass `OutboxHook` and attach it to your service's `hooks` tuple:

```python
from app_prebuilt_outbox.hooks import OutboxHook, OutboxHookEventTypeDict
from app_prebuilt_outbox.repo import OutboxRepository
from app_prebuilt_outbox.models import Outbox
from app_layer_base.base.services.base import BaseService

BOOK_EVENTS: OutboxHookEventTypeDict = {
    "CREATE": "BOOK_CREATED",
    "UPDATE": "BOOK_UPDATED",
    "DELETE": "BOOK_DELETED",
}


class BookOutboxHook(OutboxHook[Book]):
    def payload(self, op: str, obj: Book, identity: str) -> dict:
        return {
            "book_id": str(obj.id),
            "title": obj.title,
            "operation": op,
        }


class BookService(BaseService[Book, BookCreate, BookUpdate]):
    hooks = (
        BookOutboxHook(
            repo=OutboxRepository(Outbox),
            event_types=BOOK_EVENTS,
            aggregate_type="Book",
        ),
    )
```

## Step 2: Configure Background Relay

The relay is transport-agnostic. Inject any `async (event_type, DomainEvent) -> None` callable:

```python
from functools import partial
from fastapi import FastAPI
from app_prebuilt_outbox.scheduler import scheduler_lifespan, make_faststream_publisher

# FastStream publisher:
publisher = make_faststream_publisher(broker)

# Lifespan starts processor and zombie-resolver jobs:
app = FastAPI(lifespan=partial(scheduler_lifespan, publisher=publisher))
```
