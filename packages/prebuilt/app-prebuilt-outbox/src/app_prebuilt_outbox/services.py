from typing import Annotated
from uuid import UUID

from app_layer_base.utils.time_util import get_current_utc_time
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .models import EventStatus, Outbox
from .repos import OutboxRepository
from .schemas import OutboxCreate, OutboxUpdate


class OutboxService:
    def __init__(self, repo: Annotated[OutboxRepository, Depends()]):
        self._repo = repo

    @property
    def repo(self) -> OutboxRepository:
        return self._repo

    async def add_event(
        self,
        session: AsyncSession,
        event_data: OutboxCreate,
    ) -> Outbox:
        """
        Adds a new event to the outbox table.
        This should be called within the same transaction as the business logic
        that generates the event.
        """
        return await self.repo.create(session, obj_in=event_data)

    async def update_event_status(
        self,
        session: AsyncSession,
        event_id: UUID,
        status: EventStatus,
        retry_count: int | None = None,
    ) -> Outbox | None:
        """
        Legacy administrative update for unclaimed events only.
        Relay workers must use claim-token-fenced completion instead.
        """
        update_data = OutboxUpdate(status=status)
        if status == EventStatus.PUBLISHED:
            update_data.processed_at = get_current_utc_time()

        if retry_count is not None:
            update_data.retry_count = retry_count

        return await self.repo.update_unclaimed_status(session, event_id, update_data)
