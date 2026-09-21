# app-prebuilt-outbox setup

```bash
uv add "git+https://github.com/mjkimR/app-common.git@<release-tag>#subdirectory=packages/prebuilt/app-prebuilt-outbox"
```

Register `app_prebuilt_outbox.models` in the application's Alembic metadata and
migrate before starting workers. Runtime schema creation is not provided.
Supported databases: PostgreSQL and SQLite 3.35+ (UPDATE RETURNING). Use independent
connections for concurrent workers; a shared in-memory SQLite connection is unsuitable.

For an existing outbox table, stop all old processors/reapers before upgrading. Old
workers do not honor claim tokens and must never overlap with new workers. Add these
nullable columns in the consuming application's migration:

| Column | SQLAlchemy type |
|---|---|
| next_attempt_at | DateTime(timezone=True) |
| claim_token | UUID(as_uuid=True) |
| lease_expires_at | DateTime(timezone=True) |
| last_error | String(255) |

Add `ix_outbox_pending_due` on (status, next_attempt_at, created_at) and
`ix_outbox_lease_expiry` on (status, lease_expires_at). No enum values change.
Existing PENDING rows are due immediately. FAILED rows require explicit replay.
Tokenless PROCESSING rows are recovered after the legacy updated_at timeout
(default one hour), and may be redelivered. Do not reset them while old workers run.

Configure RelayOptions for batch_size, max_attempts, retry base/cap, lease,
heartbeat, publish timeout, legacy recovery timeout and shutdown timeout. Defaults
are 10 events, 3 attempts, 5/300-second backoff, 60-second lease, 15-second heartbeat,
300-second publish timeout, 3600-second legacy timeout and 30-second shutdown grace.
The scheduler polls processing every 5 seconds and recovery every 600 seconds by
default. Tune both polling intervals to the required latency. Keep clocks in UTC
and synchronized across workers; inject the clock only for controlled use/testing.
