# Upgrading an existing outbox table

This change is additive at the schema level, but old and new relay workers must not
run together: old workers complete by event ID without checking a claim token.

1. Stop/drain all old processor and zombie-resolver instances. Stop application
   processes too if they run those jobs in their lifespan. Do not let an old worker
   resume after the new workers start.
2. In the consuming application's Alembic revision, add the four nullable columns
   and two indexes below. No status enum values change and no event rows are deleted.
3. Start the new code after the migration is committed. Existing PENDING rows with
   NULL next_attempt_at are immediately eligible. Existing FAILED rows remain terminal
   until explicitly replayed.
4. Old PROCESSING rows have no lease. The new reaper recovers them after updated_at is
   older than `legacy_timeout_seconds` (default one hour), counting one failed attempt.
   A past publisher may already have sent them; recovery can redeliver the same event ID.

Adapt this migration body to your application's revision ID/dependencies:

```python
import sqlalchemy as sa
from alembic import op


def upgrade():
    op.add_column("outbox", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox", sa.Column("claim_token", sa.UUID(as_uuid=True), nullable=True))
    op.add_column("outbox", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("outbox", sa.Column("last_error", sa.String(255), nullable=True))
    op.create_index("ix_outbox_pending_due", "outbox", ["status", "next_attempt_at", "created_at"])
    op.create_index("ix_outbox_lease_expiry", "outbox", ["status", "lease_expires_at"])
```

Use SQLite's supported Alembic batch operations if required by your application's
migration setup. Review generated migrations against these names. The model's new
columns are nullable without a runtime backfill, so capture-only writers can continue
using their previous insert shape after the relay workers have stopped.

There is no automatic downgrade: stopping/replacing relay workers changes delivery
semantics. Before removing columns or returning to old code, stop new workers and
reconcile outstanding PROCESSING/retry rows explicitly. Do not silently remove retry
schedules or claim ownership while any worker is active.
