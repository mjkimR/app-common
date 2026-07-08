import datetime
from datetime import UTC, timedelta

from app_prebuilt_outbox.models import EventStatus, Outbox
from app_prebuilt_outbox.repos import OutboxRepository


def _make(i: int, status: EventStatus = EventStatus.PENDING, created_at=None) -> Outbox:
    kwargs = {}
    if created_at is not None:
        kwargs["created_at"] = created_at
    return Outbox(
        aggregate_type="Item",
        aggregate_id=f"item-{i}",
        event_type="ITEM_CREATED",
        payload={"n": i},
        status=status,
        **kwargs,
    )


async def _seed(session, rows: list[Outbox]) -> None:
    session.add_all(rows)
    await session.commit()


class TestGetAndLockPendingEvents:
    async def test_returns_only_pending(self, session):
        repo = OutboxRepository()
        await _seed(
            session,
            [
                _make(0, EventStatus.PENDING),
                _make(1, EventStatus.PENDING),
                _make(2, EventStatus.PROCESSING),
                _make(3, EventStatus.PUBLISHED),
                _make(4, EventStatus.FAILED),
            ],
        )

        events = await repo.get_and_lock_pending_events(session)

        assert {e.aggregate_id for e in events} == {"item-0", "item-1"}
        assert all(e.status == EventStatus.PENDING for e in events)

    async def test_respects_limit(self, session):
        repo = OutboxRepository()
        await _seed(session, [_make(i) for i in range(5)])

        events = await repo.get_and_lock_pending_events(session, limit=3)

        assert len(events) == 3

    async def test_orders_by_created_at(self, session):
        repo = OutboxRepository()
        now = datetime.datetime.now(UTC)
        await _seed(
            session,
            [
                _make(3, created_at=now + timedelta(seconds=30)),
                _make(1, created_at=now + timedelta(seconds=10)),
                _make(2, created_at=now + timedelta(seconds=20)),
            ],
        )

        events = await repo.get_and_lock_pending_events(session)

        assert [e.aggregate_id for e in events] == ["item-1", "item-2", "item-3"]


class TestGetZombieEvents:
    async def test_returns_only_processing(self, session):
        repo = OutboxRepository()
        await _seed(
            session,
            [
                _make(0, EventStatus.PROCESSING),
                _make(1, EventStatus.PROCESSING),
                _make(2, EventStatus.PENDING),
                _make(3, EventStatus.PUBLISHED),
            ],
        )

        # A threshold in the future makes every PROCESSING row count as stale.
        threshold = datetime.datetime.now(UTC) + timedelta(hours=1)
        zombies = await repo.get_zombie_events(session, threshold)

        assert {e.aggregate_id for e in zombies} == {"item-0", "item-1"}

    async def test_excludes_recently_updated(self, session):
        repo = OutboxRepository()
        await _seed(session, [_make(0, EventStatus.PROCESSING)])

        # A threshold in the past excludes rows updated "now".
        threshold = datetime.datetime.now(UTC) - timedelta(hours=1)
        zombies = await repo.get_zombie_events(session, threshold)

        assert zombies == []
