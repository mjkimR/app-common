# app-prebuilt-outbox

Transactional capture and an at-least-once relay for app-layer-base applications.
Write an event in the **same transaction** as the business change; the relay commits
a short claim transaction, publishes outside the database transaction, then records
completion only while it still owns the claim. No broker, consumer inbox or search
integration is installed.

## Install and migrate

```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/prebuilt/app-prebuilt-outbox"
```

Register `app_prebuilt_outbox.models` before your application's Alembic metadata
is read. Apply migrations before starting the relay; this package never creates or
migrates runtime tables. SQLite 3.35+ and PostgreSQL are supported. For existing
outbox tables, see [the lease migration instructions](migrations.md).

## Capture events

`OutboxService.add_event(session, OutboxCreate(...))` and `OutboxHook` use the caller's
session without committing it. This supports non-CRUD commands as well as CRUD hooks.

```python
from app_prebuilt_outbox.repos import OutboxRepository
from app_prebuilt_outbox.schemas import OutboxCreate
from app_prebuilt_outbox.services import OutboxService

outbox = OutboxService(OutboxRepository())
# Inside the transaction that also performs the business write:
await outbox.add_event(
    session,
    OutboxCreate(
        aggregate_type="Book",
        aggregate_id=str(book.id),
        event_type="BOOK_UPDATED",
        payload={"book_id": str(book.id)},
    ),
)
```

For CRUD services, subclass `OutboxHook[Book, BaseContextKwargs]`, implement
`payload(op, obj, identity)`, and attach `BookOutboxHook(outbox_repo, event_types)`
to the service's `hooks` tuple. `event_types` maps CREATE/UPDATE/DELETE to event names.
The hook writes one event per actually changed object, including bulk operations.
It never emits for missing updates or unsuccessful deletions.

## Use the relay

```python
from app_prebuilt_outbox import OutboxRelay, RelayOptions
from app_prebuilt_outbox.scheduler import make_faststream_publisher

relay = OutboxRelay(
    make_faststream_publisher(broker),
    session_maker=application_session_maker,
    options=RelayOptions(
        batch_size=10,
        max_attempts=3,
        retry_base_seconds=5,
        retry_max_seconds=300,
        lease_seconds=60,
        heartbeat_seconds=15,
        publish_timeout_seconds=300,
    ),
)
report = await relay.run_once()
recovered = await relay.recover()
# Explicit administrative replay after investigating a terminal failure:
requeued = await relay.requeue_failed(event_id)
```

The injected publisher is any async `(event_type, DomainEvent) -> None` callable.
It must return only after the transport acknowledges publication. Each attempt uses
the same event ID, original creation time and persisted payload. The relay copies
publication data before committing, so `expire_on_commit=True` is supported and no
ORM object crosses into publisher I/O.

`run_once()` processes at most `batch_size` events sequentially, claiming each only
when ready to publish. It does not preclaim a batch whose leases could expire while
waiting behind another event. It returns `RelayResult(claimed, published, retried,
failed, lost)`. `recover()` returns recovery counts in `retried`/`failed`. Database
errors propagate to the caller instead of being reported as successful empty work.
A dedicated worker can schedule these operations independently of FastAPI.

## FastAPI lifecycle

```python
from functools import partial
from fastapi import FastAPI
from app_prebuilt_outbox import RelayOptions
from app_prebuilt_outbox.scheduler import scheduler_lifespan

app = FastAPI(
    lifespan=partial(
        scheduler_lifespan,
        publisher=publisher,
        session_maker=application_session_maker,
        options=RelayOptions(shutdown_timeout_seconds=30),
        process_interval_seconds=5,
        zombie_interval_seconds=600,
    )
)
```

Compose this lifespan **inside** the database and broker lifespans so both resources
remain open while active work drains. On shutdown, polling stops, no new claims are
made, and the active publication gets the configured grace period. Remaining work
is cancelled and drained; interrupted claims remain leased until recovery. Publishers
must cooperate with asyncio cancellation and use transport timeouts. Set database
connect/statement timeouts as well; the relay cannot forcibly terminate blocked
external code. The default recovery interval is ten minutes, so tune it to the desired
crash recovery latency independently of the lease duration.

The existing `process_outbox_events_job(publisher)` and `resolve_zombie_events()`
entry points remain available, with optional `session_maker`, `options` and `clock`
keyword arguments. Omitting the maker retains the app-layer-base default. Prefer
explicit injection to keep workers attached to the intended database. Do not wrap
relay calls in a business transaction or give them a maker bound to its connection.

## State and failure semantics

| State | Meaning |
|---|---|
| PENDING | New event or retry; eligible when next_attempt_at is NULL or due. |
| PROCESSING | Claimed with a random claim_token and a lease_expires_at deadline. |
| PUBLISHED | External transport acknowledged and the owning claim recorded completion. |
| FAILED | Failure budget exhausted; retained for inspection and explicit replay. |

- Claim is one atomic UPDATE with a scalar candidate subquery and RETURNING. PostgreSQL
  uses FOR UPDATE SKIP LOCKED for candidate selection. File-backed SQLite serializes
  the write statement; correctness does not rely on SQLite honoring row locks.
  Separate workers need separate connections. Concurrent use of a shared in-memory
  SQLite connection is unsupported.
- Renew and completion require matching event ID, PROCESSING state, claim token and
  an unexpired lease. Expired workers cannot renew or acknowledge, even before the
  reaper runs. After reclaim, an old token cannot overwrite the new attempt's result.
- Publisher errors and timeouts increment `retry_count`, which counts failed or expired
  attempts. Retry delays grow exponentially from `retry_base_seconds`, capped at
  `retry_max_seconds`. With `max_attempts=3`, the third failure is terminal. Successful
  delivery retains the prior failure count. A lower configured budget terminalizes
  already-exhausted pending work when next due, without publishing it again.
- Event envelope validation runs after claim commit. Invalid persisted events use
  the same retry budget/backoff with `last_error=invalid_event`, allowing other
  pending events to proceed without invoking the publisher for the invalid event.
- Heartbeats renew a live claim during slow publication. Lease loss cancels/drains the
  publisher and records no completion. Cancellation or a DB completion failure leaves
  a PROCESSING row for expiry recovery. Expiry consumes the same failure budget and
  schedules the same backoff; competing reapers cannot count the same expiry twice.
- Heartbeat DB work runs separately from publication completion/timeout monitoring.
  Slow renewal cannot turn an acknowledged publication into a publish timeout or delay
  cancelling a timed-out publisher. Both tasks drain before DB completion; cleanup
  itself can exceed the publish timeout while external resources are released.
- Caller cancellation received during publisher cleanup propagates after cleanup
  completes. Scheduler shutdown drains all owned jobs before propagating cancellation.
- `last_error` records an exception class or `invalid_event`, `publish_timeout`, `lease_expired`, or
  `retry_budget_exhausted`; raw transport errors and payloads are not persisted there.
  `processed_at` records a completed/failed/recovered attempt; it no longer means only
  successful publication. `updated_at` is explicitly maintained on relay transitions.
- `requeue_failed(id)` only changes FAILED rows, resets the budget and keeps the stable
  event ID. It cannot reset an active claim. The legacy `update_event_status` service
  method is administrative only: it refuses active claims and cannot enter PROCESSING.
  Raw repository CRUD is not a worker completion API and must not bypass these guards.

The default clock is aware UTC; tests can inject a clock. Keep worker clocks synchronized
and choose a lease with margin for scheduling/DB latency. Heartbeat intervals must be
less than half the lease. Sync host clocks and independent DB connections are runtime
requirements, not guarantees added by the Python object.

## Delivery guarantees and limits

Capture is atomic with the source transaction. **External publication and DB completion
are not atomic**: a crash after successful publication can cause redelivery. Consumers
must implement idempotence with the event ID. A claim token fences database state only;
it cannot retract an external side effect from an old worker. There is no exactly-once
or per-aggregate ordering guarantee. A failed older event can be delivered after newer
events. Applications needing ordered projections must handle source revisions/ordering
in their consumer.

FAILED is a retained database state, not a separately managed broker DLQ. Successful and
failed events are not auto-deleted. Retention, monitoring of queue age/failures, explicit
replay authorization and consumer deduplication remain application responsibilities.
No automatic connection to app-prebuilt-search or downstream applications is made.

## Validation

Run `just lint app-prebuilt-outbox`, `just check app-prebuilt-outbox`, and
`bash scripts/run-tests.sh sqlite app-prebuilt-outbox`. Run the latter with `postgres`
for real PostgreSQL locking. Coverage includes file-backed SQLite competing workers,
PostgreSQL skip-locked behavior, backoff/exhaustion, expiry recovery, old-token rejection,
heartbeat loss, publish-before-ack failure, cancellation and lifespan shutdown.
