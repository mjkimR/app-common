"""Optional FastAPI/APScheduler wiring around the independently usable relay."""

import asyncio
import logging
import math
from collections.abc import AsyncIterator, Callable, Coroutine
from contextlib import asynccontextmanager
from datetime import datetime
from functools import partial
from typing import Any

from app_layer_base.base.schemas.event import DomainEvent
from app_layer_base.utils.time_util import get_current_utc_time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .policy import RelayOptions
from .relay import EventPublisher, OutboxRelay, RelayResult, _cancel_and_drain

logger = logging.getLogger(__name__)


def make_faststream_publisher(broker: Any) -> EventPublisher:
    """Adapt an async publish(message, channel=...) transport without owning it."""

    async def publish(event_type: str, event: DomainEvent) -> None:
        channel = f"events.{event_type.lower().replace('_', '.')}"
        await broker.publish(event.to_message(), channel=channel)

    return publish


async def process_outbox_events_job(
    publisher: EventPublisher,
    *,
    session_maker: async_sessionmaker[AsyncSession] | None = None,
    options: RelayOptions | None = None,
    clock: Callable[[], datetime] = get_current_utc_time,
) -> RelayResult:
    """Compatible one-shot entry point; application DB injection is recommended."""
    return await OutboxRelay(publisher, session_maker=session_maker, options=options, clock=clock).run_once()


async def resolve_zombie_events(
    *,
    session_maker: async_sessionmaker[AsyncSession] | None = None,
    options: RelayOptions | None = None,
    clock: Callable[[], datetime] = get_current_utc_time,
) -> RelayResult:
    async def unused(event_type: str, event: DomainEvent) -> None:
        raise AssertionError("recovery must never publish")

    return await OutboxRelay(unused, session_maker=session_maker, options=options, clock=clock).recover()


@asynccontextmanager
async def scheduler_lifespan(
    app: FastAPI,
    publisher: EventPublisher,
    *,
    session_maker: async_sessionmaker[AsyncSession] | None = None,
    options: RelayOptions | None = None,
    process_interval_seconds: float = 5,
    zombie_interval_seconds: float = 600,
) -> AsyncIterator[None]:
    """Stop polling, drain active work, then cancel after the shutdown grace period.

    Compose this inside the application's DB/broker lifespans so those resources
    remain open during drain. No schema creation or source hooks are installed.
    """
    for interval in (process_interval_seconds, zombie_interval_seconds):
        if not math.isfinite(interval) or interval <= 0:
            raise ValueError("scheduler intervals must be finite and positive")
    relay = OutboxRelay(publisher, session_maker=session_maker, options=options)
    scheduler = AsyncIOScheduler()
    active: set[asyncio.Task[RelayResult]] = set()
    closing = False

    def finished(task: asyncio.Task[RelayResult]) -> None:
        active.discard(task)
        if not task.cancelled() and (exc := task.exception()) is not None:
            logger.error("Outbox relay job failed: %s", type(exc).__name__)

    async def run(job: Callable[[], Coroutine[Any, Any, RelayResult]]) -> None:
        if closing:
            return
        task = asyncio.create_task(job())
        active.add(task)
        task.add_done_callback(finished)
        # APScheduler cancels its wrapper on shutdown; keep the owned job alive
        # until our explicit grace period has elapsed.
        await asyncio.shield(task)

    scheduler.add_job(
        partial(run, relay.run_once),
        "interval",
        seconds=process_interval_seconds,
        id="process_outbox",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        partial(run, relay.recover),
        "interval",
        seconds=zombie_interval_seconds,
        id="resolve_zombies",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    try:
        yield
    finally:
        closing = True
        relay.stop()
        scheduler.shutdown(wait=False)
        pending = set(active)
        try:
            if pending:
                _, pending = await asyncio.wait(pending, timeout=relay.options.shutdown_timeout_seconds)
        finally:
            for task in pending:
                task.cancel()
            cancellation = None
            for task in pending:
                if interrupted := await _cancel_and_drain(task):
                    cancellation = interrupted
            if cancellation is not None:
                raise cancellation
