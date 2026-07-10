"""Exercises the outbox's ``SELECT ... FOR UPDATE SKIP LOCKED`` guarantee.

The outbox exists so that an event is relayed exactly once even when several
workers poll concurrently. That guarantee rests entirely on row locking in
``OutboxRepository.get_and_lock_pending_events`` / ``get_zombie_events``.

SQLite parses ``FOR UPDATE SKIP LOCKED`` and then ignores it, so running these
tests on SQLite would prove nothing -- they skip instead. A skip here means the
guarantee went UNVERIFIED on this run, not that it holds. Run ``just test-pg``.
"""

import asyncio
import datetime
from datetime import UTC, timedelta

import pytest
from app_prebuilt_outbox.models import EventStatus, Outbox
from app_prebuilt_outbox.repos import OutboxRepository
from app_prebuilt_outbox.scheduler import process_outbox_events_job
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError


@pytest.fixture(autouse=True)
def _requires_postgres(is_postgres):
    if not is_postgres:
        pytest.skip("skip_locked is a no-op on SQLite; run with --db-type postgres (just test-pg)")


async def _fail_fast_on_lock_wait(session) -> None:
    """Make the follower worker raise instead of waiting for a lock.

    ``skip_locked`` never waits, so this is inert while the code is correct. If it
    ever regresses to a plain ``FOR UPDATE``, the follower would block on the leader
    forever and hang CI; with this, it raises a DBAPIError and the test fails loudly.
    Must run inside an open transaction for ``SET LOCAL`` to apply.
    """
    await session.execute(text("SET LOCAL lock_timeout = '2s'"))


class RecordingPublisher:
    def __init__(self):
        self.calls: list[str] = []

    async def __call__(self, event_type: str, event) -> None:
        self.calls.append(event.meta["aggregate_id"])


def _event(i: int, status: EventStatus = EventStatus.PENDING) -> Outbox:
    return Outbox(
        aggregate_type="Item",
        aggregate_id=f"item-{i}",
        event_type="ITEM_CREATED",
        payload={"n": i},
        status=status,
    )


async def _seed(session, count: int, status: EventStatus = EventStatus.PENDING) -> None:
    session.add_all([_event(i, status) for i in range(count)])
    await session.commit()


def _ids(events) -> set[str]:
    return {e.aggregate_id for e in events}


class TestSkipLocked:
    async def test_second_worker_skips_rows_locked_by_the_first(self, session, session_maker):
        """Two workers polling at once must claim disjoint batches."""
        await _seed(session, 4)
        repo = OutboxRepository()

        async with session_maker() as worker_a, worker_a.begin():
            claimed_by_a = await repo.get_and_lock_pending_events(worker_a, limit=2)
            assert len(claimed_by_a) == 2

            # A still holds its row locks here, so B must step over them
            # rather than block on or re-claim them.
            async with session_maker() as worker_b, worker_b.begin():
                await _fail_fast_on_lock_wait(worker_b)
                claimed_by_b = await repo.get_and_lock_pending_events(worker_b, limit=2)

        assert len(claimed_by_b) == 2
        assert _ids(claimed_by_a).isdisjoint(_ids(claimed_by_b))
        assert _ids(claimed_by_a) | _ids(claimed_by_b) == {f"item-{i}" for i in range(4)}

    async def test_second_worker_gets_nothing_when_every_row_is_locked(self, session, session_maker):
        """The rows are skipped, not merely invisible: B sees zero, not four."""
        await _seed(session, 4)
        repo = OutboxRepository()

        async with session_maker() as worker_a, worker_a.begin():
            claimed_by_a = await repo.get_and_lock_pending_events(worker_a, limit=10)
            assert len(claimed_by_a) == 4

            async with session_maker() as worker_b, worker_b.begin():
                await _fail_fast_on_lock_wait(worker_b)
                claimed_by_b = await repo.get_and_lock_pending_events(worker_b, limit=10)

        assert claimed_by_b == []

    async def test_zombie_reaper_also_skips_locked_rows(self, session, session_maker):
        """`get_zombie_events` carries the same clause and must behave the same."""
        await _seed(session, 2, status=EventStatus.PROCESSING)

        # A threshold in the future makes every PROCESSING row count as stale.
        threshold = datetime.datetime.now(UTC) + timedelta(hours=1)
        repo = OutboxRepository()

        async with session_maker() as worker_a, worker_a.begin():
            zombies_a = await repo.get_zombie_events(worker_a, threshold, limit=10)
            assert len(zombies_a) == 2

            async with session_maker() as worker_b, worker_b.begin():
                await _fail_fast_on_lock_wait(worker_b)
                zombies_b = await repo.get_zombie_events(worker_b, threshold, limit=10)

        assert zombies_b == []

    async def test_the_rows_worker_a_holds_are_genuinely_locked(self, session, session_maker):
        """Control: without `skip_locked`, the same rows are unavailable to B.

        ``FOR UPDATE NOWAIT`` errors instead of waiting, so this proves A's locks are
        real. Without it, the assertions above could pass vacuously -- e.g. if B saw
        no rows for some reason unrelated to locking.
        """
        await _seed(session, 2)
        repo = OutboxRepository()
        nowait_stmt = select(Outbox).where(Outbox.status == EventStatus.PENDING).with_for_update(nowait=True)

        async with session_maker() as worker_a, worker_a.begin():
            await repo.get_and_lock_pending_events(worker_a, limit=10)

            async with session_maker() as worker_b:
                with pytest.raises(DBAPIError) as excinfo:
                    await worker_b.execute(nowait_stmt)
                assert "LockNotAvailableError" in str(excinfo.value)

                # Postgres aborts the transaction on error; unwind it before B closes.
                await worker_b.rollback()


class TestConcurrentRelayJobs:
    async def test_two_relay_jobs_publish_each_event_exactly_once(self, session, session_maker):
        """End-to-end: the real job function, run twice concurrently, must not double-publish."""
        await _seed(session, 6)

        publisher_a, publisher_b = RecordingPublisher(), RecordingPublisher()
        await asyncio.gather(
            process_outbox_events_job(publisher_a),
            process_outbox_events_job(publisher_b),
        )

        published = publisher_a.calls + publisher_b.calls
        assert sorted(published) == [f"item-{i}" for i in range(6)]
        assert len(published) == len(set(published)), f"event published more than once: {published}"

        async with session_maker() as check:
            rows = (await check.execute(select(Outbox))).scalars().all()
        assert all(r.status == EventStatus.PUBLISHED for r in rows)
