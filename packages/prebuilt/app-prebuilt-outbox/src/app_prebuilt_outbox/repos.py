import datetime
from collections.abc import Sequence
from uuid import UUID

from app_layer_base.base.repos.base import BaseRepository
from sqlalchemy import and_, case, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import EventStatus, Outbox
from .schemas import OutboxCreate, OutboxUpdate


class OutboxRepository(BaseRepository[Outbox, OutboxCreate, OutboxUpdate, OutboxUpdate]):
    model = Outbox

    async def get_and_lock_pending_events(self, session: AsyncSession, limit: int = 100) -> Sequence[Outbox]:
        """
        Retrieves and locks a batch of pending outbox events to prevent race conditions
        from multiple publisher instances.
        """
        stmt = (
            select(self.model)
            .where(self.model.status == EventStatus.PENDING)
            .order_by(self.model.created_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_zombie_events(
        self, session: AsyncSession, timeout_threshold: "datetime.datetime", limit: int = 100
    ) -> Sequence[Outbox]:
        """
        Retrieves events that have been stuck in PROCESSING state for too long.

        Args:
            session: Database session
            timeout_threshold: Events with updated_at before this time are considered zombies
            limit: Maximum number of events to retrieve
        """
        stmt = (
            select(self.model)
            .where(
                self.model.status == EventStatus.PROCESSING,
                self.model.updated_at < timeout_threshold,
            )
            .order_by(self.model.updated_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def claim_one(
        self, session: AsyncSession, *, now: datetime.datetime, lease_expires_at: datetime.datetime, token: UUID
    ) -> Outbox | None:
        """Atomically claim one due row; SQLite does not depend on FOR UPDATE.

        PostgreSQL skips locked candidates. SQLite serializes this single UPDATE,
        avoiding a read-then-write transaction upgrade or a process-local mutex.
        The caller must commit before sending the event to an external publisher.
        """
        due = and_(
            Outbox.status == EventStatus.PENDING,
            or_(Outbox.next_attempt_at.is_(None), Outbox.next_attempt_at <= now),
        )
        candidate = (
            select(Outbox.id)
            .where(due)
            .order_by(Outbox.created_at, Outbox.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        stmt = (
            update(Outbox)
            .where(Outbox.id == candidate.scalar_subquery(), due)
            .values(status=EventStatus.PROCESSING, claim_token=token, lease_expires_at=lease_expires_at, updated_at=now)
            .returning(Outbox)
            .execution_options(synchronize_session=False)
        )
        return (await session.scalars(stmt)).one_or_none()

    @staticmethod
    def _owned(event_id: UUID, token: UUID, now: datetime.datetime):
        return and_(
            Outbox.id == event_id,
            Outbox.status == EventStatus.PROCESSING,
            Outbox.claim_token == token,
            Outbox.lease_expires_at > now,
        )

    async def renew_claim(
        self,
        session: AsyncSession,
        event_id: UUID,
        token: UUID,
        *,
        now: datetime.datetime,
        lease_expires_at: datetime.datetime,
    ) -> bool:
        stmt = (
            update(Outbox)
            .where(self._owned(event_id, token, now))
            .values(
                lease_expires_at=lease_expires_at,
                updated_at=now,
            )
            .returning(Outbox.id)
            .execution_options(synchronize_session=False)
        )
        return (await session.scalar(stmt)) is not None

    async def finish_claim(
        self,
        session: AsyncSession,
        event_id: UUID,
        token: UUID,
        *,
        now: datetime.datetime,
        status: EventStatus,
        retry_count: int,
        next_attempt_at: datetime.datetime | None = None,
        error: str | None = None,
    ) -> bool:
        if status not in (EventStatus.PENDING, EventStatus.PUBLISHED, EventStatus.FAILED):
            raise ValueError("invalid completion status")
        stmt = (
            update(Outbox)
            .where(self._owned(event_id, token, now))
            .values(
                status=status,
                retry_count=retry_count,
                next_attempt_at=next_attempt_at,
                last_error=error,
                claim_token=None,
                lease_expires_at=None,
                processed_at=now,
                updated_at=now,
            )
            .returning(Outbox.id)
            .execution_options(synchronize_session=False)
        )
        return (await session.scalar(stmt)) is not None

    async def recover_one(
        self,
        session: AsyncSession,
        *,
        now: datetime.datetime,
        legacy_threshold: datetime.datetime,
        max_attempts: int,
        retry_schedule: Sequence[datetime.datetime],
    ) -> EventStatus | None:
        """Atomic expired-claim recovery, including tokenless pre-migration workers."""
        expired = and_(
            Outbox.status == EventStatus.PROCESSING,
            or_(
                Outbox.lease_expires_at <= now,
                and_(Outbox.lease_expires_at.is_(None), Outbox.updated_at < legacy_threshold),
            ),
        )
        candidate = (
            select(Outbox.id)
            .where(expired)
            .order_by(Outbox.updated_at, Outbox.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        exhausted = Outbox.retry_count + 1 >= max_attempts
        next_attempt = case(
            *[(Outbox.retry_count == i, at) for i, at in enumerate(retry_schedule)],
            else_=retry_schedule[-1],
        )
        stmt = (
            update(Outbox)
            .where(Outbox.id == candidate.scalar_subquery(), expired)
            .values(
                status=case((exhausted, EventStatus.FAILED), else_=EventStatus.PENDING).cast(Outbox.status.type),
                retry_count=Outbox.retry_count + 1,
                next_attempt_at=case((exhausted, None), else_=next_attempt),
                claim_token=None,
                lease_expires_at=None,
                last_error="lease_expired",
                processed_at=now,
                updated_at=now,
            )
            .returning(Outbox.status)
            .execution_options(synchronize_session=False)
        )
        return await session.scalar(stmt)

    async def requeue_failed(self, session: AsyncSession, event_id: UUID, *, now: datetime.datetime) -> bool:
        """Explicit replay resets the failure budget, retaining the stable event ID."""
        stmt = (
            update(Outbox)
            .where(Outbox.id == event_id, Outbox.status == EventStatus.FAILED)
            .values(
                status=EventStatus.PENDING,
                retry_count=0,
                next_attempt_at=now,
                claim_token=None,
                lease_expires_at=None,
                processed_at=None,
                last_error=None,
                updated_at=now,
            )
            .returning(Outbox.id)
            .execution_options(synchronize_session=False)
        )
        return (await session.scalar(stmt)) is not None

    async def update_unclaimed_status(
        self,
        session: AsyncSession,
        event_id: UUID,
        values: OutboxUpdate,
    ) -> Outbox | None:
        """Legacy administrative API; active claims may only use token-fenced operations."""
        if values.status == EventStatus.PROCESSING:
            raise ValueError("Use claim_one to enter PROCESSING with a lease and token")
        stmt = (
            update(Outbox)
            .where(
                Outbox.id == event_id,
                Outbox.status != EventStatus.PROCESSING,
                Outbox.claim_token.is_(None),
            )
            .values(**values.model_dump(exclude_unset=True))
            .returning(Outbox)
            .execution_options(populate_existing=True)
        )
        return (await session.scalars(stmt)).one_or_none()
