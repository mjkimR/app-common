import datetime
import uuid
from datetime import UTC, timedelta

from app_layer_base.base.schemas.event import DomainEvent
from app_layer_base.core.database.transaction import AsyncTransaction
from app_prebuilt_outbox.models import EventStatus, Outbox
from app_prebuilt_outbox.scheduler import (
    make_faststream_publisher,
    process_outbox_events_job,
    resolve_zombie_events,
)
from sqlalchemy import select


class RecordingPublisher:
    def __init__(self):
        self.calls: list[tuple[str, DomainEvent]] = []

    async def __call__(self, event_type: str, event: DomainEvent) -> None:
        self.calls.append((event_type, event))


class FailingPublisher:
    async def __call__(self, event_type: str, event: DomainEvent) -> None:
        raise RuntimeError("publish boom")


def _pending(i: int) -> Outbox:
    return Outbox(
        aggregate_type="Item",
        aggregate_id=f"item-{i}",
        event_type="ITEM_CREATED",
        payload={"n": i},
        status=EventStatus.PENDING,
    )


async def _read_all() -> list[Outbox]:
    async with AsyncTransaction() as session:
        result = await session.execute(select(Outbox).order_by(Outbox.aggregate_id))
        return list(result.scalars().all())


class TestProcessOutboxEventsJob:
    async def test_publishes_pending_events(self, session):
        session.add_all([_pending(0), _pending(1), _pending(2)])
        await session.commit()

        publisher = RecordingPublisher()
        await process_outbox_events_job(publisher)

        assert len(publisher.calls) == 3
        assert {t for t, _ in publisher.calls} == {"ITEM_CREATED"}

        rows = await _read_all()
        assert all(r.status == EventStatus.PUBLISHED for r in rows)
        assert all(r.processed_at is not None for r in rows)

    async def test_marks_failed_when_publisher_raises(self, session):
        session.add_all([_pending(0), _pending(1)])
        await session.commit()

        await process_outbox_events_job(FailingPublisher())

        rows = await _read_all()
        assert all(r.status == EventStatus.FAILED for r in rows)
        assert all(r.retry_count == 1 for r in rows)


class TestResolveZombieEvents:
    async def test_resets_retryable_and_dlqs_exhausted(self, session):
        stale = datetime.datetime.now(UTC) - timedelta(hours=2)
        retryable = Outbox(
            aggregate_type="Item",
            aggregate_id="retryable",
            event_type="ITEM_CREATED",
            payload={},
            status=EventStatus.PROCESSING,
            retry_count=0,
            updated_at=stale,
        )
        exhausted = Outbox(
            aggregate_type="Item",
            aggregate_id="exhausted",
            event_type="ITEM_CREATED",
            payload={},
            status=EventStatus.PROCESSING,
            retry_count=2,  # +1 in resolver reaches the max (3) -> DLQ
            updated_at=stale,
        )
        session.add_all([retryable, exhausted])
        await session.commit()

        await resolve_zombie_events()

        rows = {r.aggregate_id: r for r in await _read_all()}
        assert rows["retryable"].status == EventStatus.PENDING
        assert rows["retryable"].retry_count == 1
        assert rows["exhausted"].status == EventStatus.FAILED
        assert rows["exhausted"].retry_count == 3


class TestMakeFaststreamPublisher:
    async def test_derives_channel_from_event_type(self):
        published: list[tuple[object, str]] = []

        class FakeBroker:
            async def publish(self, message, channel):
                published.append((message, channel))

        publisher = make_faststream_publisher(FakeBroker())
        event = DomainEvent(id=uuid.uuid4(), source="/item/outbox", type="ITEM_CREATED", data={"n": 1}, meta={})

        await publisher("ITEM_CREATED", event)

        assert len(published) == 1
        message, channel = published[0]
        assert channel == "events.item.created"
        assert message is not None
