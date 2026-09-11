from app_prebuilt_outbox.models import EventStatus
from app_prebuilt_outbox.repos import OutboxRepository
from app_prebuilt_outbox.schemas import OutboxCreate
from app_prebuilt_outbox.services import OutboxService


def _create_data(i: int = 0) -> OutboxCreate:
    return OutboxCreate(
        aggregate_type="Item",
        aggregate_id=f"item-{i}",
        event_type="ITEM_CREATED",
        payload={"n": i},
    )


class TestAddEvent:
    async def test_creates_pending_event(self, session):
        service = OutboxService(OutboxRepository())

        event = await service.add_event(session, _create_data(1))

        assert event.id is not None
        assert event.status == EventStatus.PENDING
        assert event.aggregate_id == "item-1"
        assert event.event_type == "ITEM_CREATED"
        assert event.retry_count == 0


class TestUpdateEventStatus:
    async def test_published_sets_processed_at(self, session):
        service = OutboxService(OutboxRepository())
        event = await service.add_event(session, _create_data())
        await session.commit()

        updated = await service.update_event_status(session, event.id, EventStatus.PUBLISHED)

        assert updated is not None
        assert updated.status == EventStatus.PUBLISHED
        assert updated.processed_at is not None

    async def test_failed_status_without_processed_at(self, session):
        service = OutboxService(OutboxRepository())
        event = await service.add_event(session, _create_data())
        await session.commit()

        updated = await service.update_event_status(session, event.id, EventStatus.FAILED, retry_count=2)

        assert updated is not None
        assert updated.status == EventStatus.FAILED
        assert updated.retry_count == 2
        assert updated.processed_at is None
