from typing import Sequence

from app_base.base.repos.base import BaseRepository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
