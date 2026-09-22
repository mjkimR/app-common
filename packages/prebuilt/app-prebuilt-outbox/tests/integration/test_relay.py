import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from app_layer_base.base.models.mixin import Base
from app_prebuilt_outbox import OutboxRelay, RelayOptions
from app_prebuilt_outbox.models import EventStatus, Outbox
from app_prebuilt_outbox.repos import OutboxRepository
from app_prebuilt_outbox.services import OutboxService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class Clock:
    def __init__(self):
        self.now = datetime.now(UTC)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


class Publisher:
    def __init__(self):
        self.events = []
        self.fail = False

    async def __call__(self, event_type, event):
        self.events.append(event.model_copy(deep=True))
        if self.fail:
            raise RuntimeError("sensitive transport details")


@pytest.fixture
async def env(concurrent_maker):
    session_maker = concurrent_maker
    clock, publisher = Clock(), Publisher()

    async def seed(count=1):
        async with session_maker.begin() as db:
            rows = [
                Outbox(aggregate_type="Item", aggregate_id=str(i), event_type="CREATED", payload={"i": i})
                for i in range(count)
            ]
            db.add_all(rows)
            await db.flush()
            return [r.id for r in rows]

    async def read():
        async with session_maker() as db:
            return list((await db.scalars(select(Outbox).order_by(Outbox.aggregate_id))).all())

    def relay(**kwargs):
        return OutboxRelay(**{"publisher": publisher, "session_maker": session_maker, "clock": clock, **kwargs})

    return SimpleNamespace(clock=clock, publisher=publisher, seed=seed, read=read, relay=relay, maker=session_maker)


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


async def test_retry_backoff_exhaustion_and_explicit_replay(env):
    e = env
    ids = await e.seed()
    e.publisher.fail = True
    relay = e.relay()
    assert (await relay.run_once()).retried == 1
    first = (await e.read())[0]
    assert first.retry_count == 1 and first.last_error == "RuntimeError"
    assert utc(first.next_attempt_at) == e.clock.now + timedelta(seconds=5)
    assert (await relay.run_once()).claimed == 0
    e.clock.advance(5)
    assert (await relay.run_once()).retried == 1
    second = (await e.read())[0]
    assert second.retry_count == 2 and utc(second.next_attempt_at) == e.clock.now + timedelta(seconds=10)
    e.clock.advance(10)
    assert (await relay.run_once()).failed == 1
    row = (await e.read())[0]
    assert row.status == EventStatus.FAILED and row.retry_count == 3
    assert row.next_attempt_at is None and row.lease_expires_at is None and row.claim_token is None
    e.clock.advance(10000)
    assert (await relay.run_once()).claimed == 0
    assert (await relay.recover()).retried == 0
    assert await relay.requeue_failed(ids[0])
    assert not await relay.requeue_failed(ids[0])
    e.publisher.fail = False
    assert (await relay.run_once()).published == 1
    assert (await e.read())[0].retry_count == 0
    assert len({event.id for event in e.publisher.events}) == 1
    assert len({event.time for event in e.publisher.events}) == 1


async def test_expire_on_commit_and_publisher_sees_durable_claim(env):
    e = env
    await e.seed()
    maker = async_sessionmaker(e.maker.kw["bind"], expire_on_commit=True)

    async def publish(event_type, event):
        rows = await e.read()
        assert rows[0].status == EventStatus.PROCESSING
        assert rows[0].claim_token is not None
        assert event.data == {"i": 0}

    assert (await e.relay(publisher=publish, session_maker=maker).run_once()).published == 1


async def test_claim_failure_rolls_back_without_publishing(env, monkeypatch):
    e = env
    await e.seed()
    relay = e.relay()
    original = relay.repo.claim_one

    async def fail(*args, **kwargs):
        await original(*args, **kwargs)
        raise RuntimeError("DB claim error")

    monkeypatch.setattr(relay.repo, "claim_one", fail)
    with pytest.raises(RuntimeError, match="claim error"):
        await relay.run_once()
    assert not e.publisher.events
    assert (await e.read())[0].status == EventStatus.PENDING


async def test_publish_success_before_ack_failure_is_redelivered_with_same_identity(env, monkeypatch):
    e = env
    await e.seed()
    relay = e.relay()

    async def fail(*args, **kwargs):
        raise RuntimeError("DB completion unavailable")

    monkeypatch.setattr(relay.repo, "finish_claim", fail)
    with pytest.raises(RuntimeError, match="completion unavailable"):
        await relay.run_once()
    assert (await e.read())[0].status == EventStatus.PROCESSING
    assert len(e.publisher.events) == 1
    e.clock.advance(61)
    fresh = e.relay()
    assert (await fresh.recover()).retried == 1
    e.clock.advance(5)
    assert (await fresh.run_once()).published == 1
    assert len(e.publisher.events) == 2
    assert e.publisher.events[0] == e.publisher.events[1]


async def test_expired_token_cannot_renew_or_complete_even_before_recovery(env):
    e = env
    ids = await e.seed()
    repo, token = OutboxRepository(), uuid4()
    async with e.maker.begin() as db:
        await repo.claim_one(db, now=e.clock.now, lease_expires_at=e.clock.now + timedelta(seconds=60), token=token)
    e.clock.advance(60)
    async with e.maker.begin() as db:
        assert not await repo.renew_claim(
            db, ids[0], token, now=e.clock.now, lease_expires_at=e.clock.now + timedelta(seconds=60)
        )
        assert not await repo.finish_claim(
            db, ids[0], token, now=e.clock.now, status=EventStatus.PUBLISHED, retry_count=0
        )
    assert (await e.relay().recover()).retried == 1
    assert (await e.relay().recover()).retried == 0
    row = (await e.read())[0]
    assert row.retry_count == 1 and row.last_error == "lease_expired"


async def test_late_worker_cannot_overwrite_reclaimed_success(env):
    e = env
    await e.seed()
    entered, release = asyncio.Event(), asyncio.Event()

    async def slow(event_type, event):
        entered.set()
        await release.wait()

    old = asyncio.create_task(e.relay(publisher=slow).run_once())
    await asyncio.wait_for(entered.wait(), 5)
    try:
        e.clock.advance(61)
        assert (await e.relay().recover()).retried == 1
        e.clock.advance(5)
        assert (await e.relay().run_once()).published == 1
    finally:
        release.set()
    result = await old
    assert result.lost == 1 and result.published == 0
    row = (await e.read())[0]
    assert row.status == EventStatus.PUBLISHED and row.retry_count == 1


async def test_heartbeat_extends_lease_during_publication(env, monkeypatch):
    e = env
    await e.seed()
    entered, renewed, release = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def slow(event_type, event):
        entered.set()
        await release.wait()

    relay = e.relay(publisher=slow, options=RelayOptions(heartbeat_seconds=0.01))
    original = relay._renew

    async def renew(*args, **kwargs):
        result = await original(*args, **kwargs)
        renewed.set()
        return result

    monkeypatch.setattr(relay, "_renew", renew)
    task = asyncio.create_task(relay.run_once())
    await asyncio.wait_for(entered.wait(), 5)
    e.clock.advance(10)
    try:
        await asyncio.wait_for(renewed.wait(), 5)
        row = (await e.read())[0]
        assert utc(row.lease_expires_at) == e.clock.now + timedelta(seconds=60)
        assert (await e.relay().recover()).retried == 0
    finally:
        release.set()
    assert (await task).published == 1


async def test_timeout_and_cancellation_do_not_leave_orphan_publishers(env):
    e = env
    await e.seed()
    cancelled = asyncio.Event()

    async def forever(event_type, event):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    relay = e.relay(publisher=forever, options=RelayOptions(publish_timeout_seconds=0.03))
    assert (await relay.run_once()).retried == 1
    assert cancelled.is_set()
    assert (await e.read())[0].last_error == "publish_timeout"
    e.clock.advance(5)
    entered = asyncio.Event()
    cancelled.clear()

    async def cancellable(event_type, event):
        entered.set()
        await forever(event_type, event)

    task = asyncio.create_task(e.relay(publisher=cancellable).run_once())
    await asyncio.wait_for(entered.wait(), 5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()
    assert (await e.read())[0].status == EventStatus.PROCESSING
    e.clock.advance(61)
    assert (await e.relay().recover()).retried == 1


@pytest.mark.parametrize("publish_succeeds", [True, False])
async def test_slow_heartbeat_does_not_block_publish_completion_or_timeout(env, monkeypatch, publish_succeeds):
    await env.seed()
    renewing, release, renewed, publisher_done = (asyncio.Event() for _ in range(4))

    async def publish(event_type, event):
        try:
            await renewing.wait()
            if not publish_succeeds:
                await asyncio.Event().wait()
        finally:
            publisher_done.set()

    relay = env.relay(
        publisher=publish,
        options=RelayOptions(heartbeat_seconds=0.01, publish_timeout_seconds=0.2),
    )

    original = relay.repo.renew_claim

    async def slow_renew(*args, **kwargs):
        result = await original(*args, **kwargs)
        renewing.set()
        try:
            await release.wait()
            return result
        finally:
            renewed.set()

    monkeypatch.setattr(relay.repo, "renew_claim", slow_renew)
    task = asyncio.create_task(relay.run_once())
    try:
        await asyncio.wait_for(renewing.wait(), 5)
        result = await asyncio.wait_for(asyncio.shield(task), 1)
        assert publisher_done.is_set() and renewed.is_set()
        row = (await env.read())[0]
        if publish_succeeds:
            assert result.published == 1 and result.retried == 0
            assert row.status == EventStatus.PUBLISHED and row.last_error is None
        else:
            assert result.retried == 1 and result.published == 0
            assert row.status == EventStatus.PENDING and row.last_error == "publish_timeout"
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_cancellation_drains_publisher_and_heartbeat_before_propagating(env, monkeypatch):
    await env.seed()
    renewing = asyncio.Event()
    cleaning = [asyncio.Event(), asyncio.Event()]
    release = [asyncio.Event(), asyncio.Event()]
    cleaned = [asyncio.Event(), asyncio.Event()]

    async def block(index):
        try:
            await asyncio.Event().wait()
        finally:
            cleaning[index].set()
            await release[index].wait()
            cleaned[index].set()

    async def publish(event_type, event):
        await block(0)

    async def renew(claim):
        renewing.set()
        await block(1)
        return True

    relay = env.relay(publisher=publish, options=RelayOptions(heartbeat_seconds=0.01))
    monkeypatch.setattr(relay, "_renew", renew)
    task = asyncio.create_task(relay.run_once())
    try:
        await asyncio.wait_for(renewing.wait(), 5)
        task.cancel()
        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in cleaning)), 5)
        for _ in range(2):
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done()
        release[0].set()
        await asyncio.wait_for(cleaned[0].wait(), 5)
        assert not task.done() and not cleaned[1].is_set()
    finally:
        for event in release:
            event.set()
        outcome = await asyncio.gather(task, return_exceptions=True)
    assert isinstance(outcome[0], asyncio.CancelledError)
    assert all(event.is_set() for event in cleaned)
    assert (await env.read())[0].status == EventStatus.PROCESSING


async def test_heartbeat_db_error_cancels_publisher_and_leaves_claim_for_recovery(env, monkeypatch):
    await env.seed()
    cancelled = asyncio.Event()

    async def publish(event_type, event):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async def fail(claim):
        raise RuntimeError("heartbeat DB unavailable")

    relay = env.relay(publisher=publish, options=RelayOptions(heartbeat_seconds=0.01))
    monkeypatch.setattr(relay, "_renew", fail)
    with pytest.raises(RuntimeError, match="heartbeat DB unavailable"):
        await relay.run_once()
    assert cancelled.is_set()
    row = (await env.read())[0]
    assert row.status == EventStatus.PROCESSING and row.retry_count == 0


async def test_administrative_status_changes_cannot_bypass_active_claim(env):
    e = env
    ids = await e.seed()
    async with e.maker.begin() as db:
        await OutboxRepository().claim_one(
            db, now=e.clock.now, lease_expires_at=e.clock.now + timedelta(seconds=60), token=uuid4()
        )
    async with e.maker.begin() as db:
        service = OutboxService(OutboxRepository())
        assert await service.update_event_status(db, ids[0], EventStatus.PUBLISHED) is None
    assert not await e.relay().requeue_failed(ids[0])
    assert (await e.read())[0].status == EventStatus.PROCESSING


@pytest.fixture
async def concurrent_maker(session_maker, session, is_postgres, tmp_path):
    if is_postgres:
        yield session_maker
    else:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'relay.db'}")
        async with engine.begin() as db:
            await db.run_sync(Base.metadata.create_all)
        try:
            yield async_sessionmaker(engine, expire_on_commit=False)
        finally:
            await engine.dispose()


async def test_independent_relays_claim_disjoint_work(concurrent_maker):
    maker = concurrent_maker
    async with maker.begin() as db:
        db.add_all(
            [Outbox(aggregate_type="Item", aggregate_id=str(i), event_type="CREATED", payload={}) for i in range(12)]
        )
    publisher = Publisher()
    results = await asyncio.gather(*[OutboxRelay(publisher, session_maker=maker).run_once() for _ in range(3)])
    assert sum(r.published for r in results) == 12
    assert len(publisher.events) == len({event.id for event in publisher.events}) == 12


async def test_concurrent_reapers_count_expiry_once(concurrent_maker):
    clock = Clock()
    maker = concurrent_maker
    async with maker.begin() as db:
        db.add(
            Outbox(
                aggregate_type="Item",
                aggregate_id="1",
                event_type="CREATED",
                payload={},
                status=EventStatus.PROCESSING,
                claim_token=uuid4(),
                lease_expires_at=clock.now,
            )
        )
    results = await asyncio.gather(
        *[OutboxRelay(Publisher(), session_maker=maker, clock=clock).recover() for _ in range(3)]
    )
    assert sum(r.retried for r in results) == 1
    async with maker() as db:
        assert (await db.scalars(select(Outbox))).one().retry_count == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"batch_size": 0},
        {"max_attempts": 0},
        {"max_attempts": True},
        {"retry_base_seconds": 0},
        {"retry_max_seconds": 1},
        {"heartbeat_seconds": 30},
        {"lease_seconds": float("nan")},
        {"publish_timeout_seconds": float("inf")},
    ],
)
def test_invalid_options(kwargs):
    with pytest.raises(ValueError):
        RelayOptions(**kwargs)


def test_backoff_is_capped():
    options = replace(RelayOptions(), max_attempts=20)
    now = datetime.now(UTC)
    assert (options.retry_at(now, 20) - now).total_seconds() == 300


async def test_claim_and_recovery_are_bounded_to_one_row(env):
    e = env
    await e.seed(6)
    repo = OutboxRepository()
    for _ in range(2):
        async with e.maker.begin() as db:
            assert (
                await repo.claim_one(
                    db, now=e.clock.now, token=uuid4(), lease_expires_at=e.clock.now + timedelta(seconds=60)
                )
                is not None
            )
    rows = await e.read()
    assert sum(row.status == EventStatus.PROCESSING for row in rows) == 2
    e.clock.advance(61)
    result = await e.relay(options=RelayOptions(batch_size=1)).recover()
    assert result.retried == 1
    rows = await e.read()
    assert sum(row.status == EventStatus.PROCESSING for row in rows) == 1
    assert sum(row.retry_count for row in rows) == 1


async def test_recovery_exhaustion_uses_failure_budget(env):
    e = env
    await e.seed()
    repo = OutboxRepository()
    async with e.maker.begin() as db:
        await repo.claim_one(db, now=e.clock.now, token=uuid4(), lease_expires_at=e.clock.now + timedelta(seconds=60))
    e.clock.advance(61)
    result = await e.relay(options=RelayOptions(max_attempts=1)).recover()
    assert result.failed == 1 and result.retried == 0
    row = (await e.read())[0]
    assert row.status == EventStatus.FAILED and row.next_attempt_at is None


async def test_heartbeat_loss_stops_publisher_and_never_acknowledges(env, monkeypatch):
    e = env
    await e.seed()
    cancelled = asyncio.Event()

    async def publish(event_type, event):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    relay = e.relay(publisher=publish, options=RelayOptions(heartbeat_seconds=0.01))

    async def lost(*args, **kwargs):
        return False

    monkeypatch.setattr(relay.repo, "renew_claim", lost)
    result = await relay.run_once()
    assert result.lost == 1 and result.published == 0
    assert cancelled.is_set()
    assert (await e.read())[0].status == EventStatus.PROCESSING


@pytest.mark.parametrize(
    "invalid",
    [
        {"id": UUID("a0000000-0000-1000-8000-000000000001")},
        {"id": UUID("01890a5d-ac9a-7a2d-8bcc-09e638c14b03")},
        {"payload": ["not an event object"]},
    ],
)
async def test_invalid_envelope_consumes_retry_budget_without_blocking_queue(env, invalid):
    e = env
    async with e.maker.begin() as db:
        db.add(
            Outbox(
                **{
                    "aggregate_type": "Item",
                    "aggregate_id": "bad",
                    "event_type": "CREATED",
                    "payload": {},
                    "created_at": e.clock.now - timedelta(seconds=1),
                    **invalid,
                }
            )
        )
        db.add(Outbox(aggregate_type="Item", aggregate_id="good", event_type="CREATED", payload={}))
    relay = e.relay()
    result = await relay.run_once()
    assert (result.claimed, result.retried, result.published) == (2, 1, 1)
    bad, good = await e.read()
    assert bad.status == EventStatus.PENDING and bad.retry_count == 1 and bad.last_error == "invalid_event"
    assert bad.claim_token is None and bad.next_attempt_at is not None
    assert good.status == EventStatus.PUBLISHED
    assert [event.meta["aggregate_id"] for event in e.publisher.events] == ["good"]
    assert (await relay.run_once()).claimed == 0
    e.clock.advance(5)
    assert (await relay.run_once()).retried == 1
    e.clock.advance(10)
    assert (await relay.run_once()).failed == 1
    bad, good = await e.read()
    assert bad.status == EventStatus.FAILED and bad.retry_count == 3
    assert len(e.publisher.events) == 1


@pytest.mark.parametrize("cause", ["timeout", "lease_loss"])
@pytest.mark.parametrize("reraise_child_cancel", [False, True])
async def test_caller_cancel_during_publisher_cleanup_propagates_after_drain(
    env,
    monkeypatch,
    cause,
    reraise_child_cancel,
):
    e = env
    async with e.maker.begin() as db:
        db.add_all(
            [
                Outbox(
                    aggregate_type="Item",
                    aggregate_id=str(i),
                    event_type="CREATED",
                    payload={"i": i},
                    created_at=e.clock.now + timedelta(seconds=i),
                )
                for i in range(2)
            ]
        )
    cleaning, release, cleaned = asyncio.Event(), asyncio.Event(), asyncio.Event()
    calls = []

    async def publish(event_type, event):
        calls.append(event.data["i"])
        if event.data["i"] == 0:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cleaning.set()
                await release.wait()
                cleaned.set()
                if reraise_child_cancel:
                    raise

    options = RelayOptions(publish_timeout_seconds=0.03) if cause == "timeout" else RelayOptions(heartbeat_seconds=0.01)
    relay = e.relay(publisher=publish, options=options)
    if cause == "lease_loss":

        async def lose_lease(*args, **kwargs):
            return False

        monkeypatch.setattr(relay.repo, "renew_claim", lose_lease)
    task = asyncio.create_task(relay.run_once())
    await asyncio.wait_for(cleaning.wait(), 5)
    try:
        for _ in range(2):
            task.cancel()
            await asyncio.sleep(0)
            assert not task.done() and not cleaned.is_set()
    finally:
        release.set()
        outcome = await asyncio.gather(task, return_exceptions=True)
    assert isinstance(outcome[0], asyncio.CancelledError)
    assert cleaned.is_set() and calls == [0]
    first, second = await e.read()
    assert first.status == EventStatus.PROCESSING and first.retry_count == 0
    assert second.status == EventStatus.PENDING and second.claim_token is None
    e.clock.advance(61)
    assert (await e.relay().recover()).retried == 1
