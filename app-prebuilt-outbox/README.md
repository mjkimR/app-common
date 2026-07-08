# app-prebuilt-outbox

A Transactional Outbox implementation for [`app-layer-base`](../app-layer-base/README.md): domain events are persisted in the **same database transaction** as your business writes, then a background relay publishes them to whatever transport you inject. This guarantees an event is never lost or published without its write committing.

## Installation

```bash
uv add "git+https://github.com/mjkimR/app-common.git@main#subdirectory=app-prebuilt-outbox"
```

Depends on `app-layer-base`, `sqlalchemy` and `apscheduler`. It is **transport-agnostic** — it does not depend on any message-broker package.

## How it works

1. **Capture** — mix `BaseOutboxHook` into a feature's service. Its `create`/`update`/`delete` hooks write an `Outbox` row in the same session as the business change, so the event and the data commit atomically.
2. **Relay** — `scheduler_lifespan` runs two background jobs: a processor that claims pending events with `FOR UPDATE SKIP LOCKED` and publishes them, and a zombie-resolver that resets stuck events or moves exhausted ones to a dead-letter state.

The relay does not own a broker; you inject an `EventPublisher` (any `async (event_type, DomainEvent) -> None` callable), so the outbox works with FastStream, a task queue, an HTTP webhook, etc.

## Usage

```python
from functools import partial
from fastapi import FastAPI
from app_prebuilt_outbox.scheduler import scheduler_lifespan, make_faststream_publisher

# `broker` is any object with an awaitable `publish(message, channel=...)`.
publisher = make_faststream_publisher(broker)
app = FastAPI(lifespan=partial(scheduler_lifespan, publisher=publisher))
```

To emit events, add the hook to a service (implement `_get_outbox_payload`, `outbox_repo` and `_event_type_dict`); every create/update/delete on that aggregate then produces an outbox row.

## Public API

- `BaseOutboxHook` — service mixin that emits outbox rows on create/update/delete
- `OutboxRepository`, `OutboxService`, `Outbox`, `EventStatus` — persistence layer
- `scheduler_lifespan(app, publisher, *, process_interval_seconds=5, zombie_interval_seconds=600)` — FastAPI lifespan running the relay
- `EventPublisher` — the transport interface you implement/inject
- `make_faststream_publisher(broker)` — ready-made publisher over a FastStream-style broker

> The relay is intentionally simple (fixed intervals, no backoff); harden it before high-volume production use.
