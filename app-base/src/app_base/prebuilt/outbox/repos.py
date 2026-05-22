import datetime
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app_base.base.repos.base import BaseRepository

from .models import EventStatus, Outbox
from .schemas import OutboxCreate, OutboxUpdate


class OutboxRepository(BaseRepository[Outbox, OutboxCreate, OutboxUpdate]):
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
