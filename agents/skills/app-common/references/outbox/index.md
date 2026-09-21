# app-prebuilt-outbox

Use transactional capture plus an independently scheduled at-least-once relay. No
broker or search integration is installed. [Setup and migration](setup.md) is required
before starting workers against an existing outbox table.

## Capture

Call `OutboxService(OutboxRepository()).add_event(session, OutboxCreate(...))` from
non-CRUD commands using the same session as the business write. It does not commit.
For CRUD services, add an OutboxHook to the hooks tuple:

```python
from app_layer_base.base.services.hooks import BaseContextKwargs, Operation
from app_prebuilt_outbox.hooks import OutboxHook, OutboxHookEventTypeDict
from app_prebuilt_outbox.repos import OutboxRepository
from app_prebuilt_outbox.schemas import OutboxIdentityDict

BOOK_EVENTS: OutboxHookEventTypeDict = {
    "CREATE": "BOOK_CREATED", "UPDATE": "BOOK_UPDATED", "DELETE": "BOOK_DELETED",
}


class BookOutboxHook(OutboxHook[Book, BaseContextKwargs]):
    def payload(self, op: Operation[BaseContextKwargs], obj: Book, identity: OutboxIdentityDict) -> dict:
        return {"book_id": str(obj.id), "operation": identity["event_type"]}


# Add this instance to your service's hooks tuple:
book_outbox_hook = BookOutboxHook(OutboxRepository(), BOOK_EVENTS)
```

## Relay

```python
from app_prebuilt_outbox import OutboxRelay, RelayOptions

relay = OutboxRelay(publisher, session_maker=application_session_maker, options=RelayOptions())
report = await relay.run_once()
recovered = await relay.recover()
# Explicit administrative replay of a terminal failure, retaining its event ID:
requeued = await relay.requeue_failed(event_id)
```

- Publisher: async `(event_type, DomainEvent) -> None`; return after transport acknowledgement.
- Each event is claimed immediately before publication. No DB transaction spans publisher I/O.
- Failed/expired attempts use capped exponential backoff, then FAILED after max_attempts (default 3).
- Invalid persisted event envelopes consume the same retry budget with last_error=invalid_event; validation happens after claim commit so other events can proceed.
- Claim token and unexpired lease are required for renewal/completion. Heartbeat loss cancels the publisher. Expired or reclaimed workers cannot overwrite newer DB state.
- `RelayResult` exposes claimed/published/retried/failed/lost counts. DB errors propagate. Transport failure classes and lease/timeout reasons are retained in last_error without raw payload/error text.
- Retry/replay uses the stable event ID and creation time. External publish and DB completion are not atomic; consumers must deduplicate. No exactly-once or aggregate ordering guarantee.
- PostgreSQL uses SKIP LOCKED plus atomic UPDATE; SQLite uses the atomic statement and requires independent connections (file-backed for concurrent workers). Do not share one in-memory connection across concurrent relay tasks.
- Inject a session maker for the intended database; do not wrap relay calls in a business transaction. Default-maker compatibility remains available in scheduler entry points.
- `scheduler_lifespan(..., session_maker=..., options=...)` stops polling and drains active publication before cancelling after the shutdown grace period. Keep DB and broker resources open until it exits. Publishers must cooperate with cancellation and configure transport timeouts.
- Caller cancellation during cleanup is propagated after the publisher (and, on scheduler shutdown, all owned jobs) has been drained.
- The old update_event_status service API is administrative only and refuses active claims. Worker completion must use token-fenced relay operations. Do not update status through raw CRUD from a worker.
- Retention, monitoring, replay authorization, consumer deduplication and revision/ordering policies remain application-owned. FAILED is retained in the DB, not a separate broker DLQ.
