import datetime
import logging
from contextlib import asynccontextmanager
from datetime import UTC
from functools import partial
from typing import Any, Protocol

from app_layer_base.base.schemas.event import DomainEvent
from app_layer_base.core.database.transaction import AsyncTransaction
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from .models import EventStatus
from .repos import OutboxRepository

logger = logging.getLogger(__name__)
_ZOMBIE_MAX_RETRIES = 3
_ZOMBIE_TIMEOUT = 60 * 60  # 1 hour


class EventPublisher(Protocol):
    """Transport-agnostic publisher injected by the consumer.

    The outbox relay does not own a message broker. The consumer supplies a
    callable that knows how to publish a ``DomainEvent`` over whatever transport
    it uses (a FastStream broker, a Taskiq queue, an HTTP webhook, ...). This keeps
    the outbox package standalone and free of any broker dependency.

    See :func:`make_faststream_publisher` for a ready-made adapter over a
    FastStream-style broker.
    """

    async def __call__(self, event_type: str, event: DomainEvent) -> None: ...


def make_faststream_publisher(broker: Any) -> EventPublisher:
    """Build an :class:`EventPublisher` over a FastStream-style broker.

    ``broker`` only needs an awaitable ``publish(message, channel=...)`` method,
    so any object honoring that contract works without importing FastStream here.
    The channel name is derived from the event type (e.g. ``item_created`` ->
    ``events.item.created``).
    """

    async def _publish(event_type: str, event: DomainEvent) -> None:
        channel = f"events.{event_type.lower().replace('_', '.')}"
        await broker.publish(event.to_message(), channel=channel)
        logger.debug(f"Event dispatched: {event_type} -> {channel}")

    return _publish


async def process_outbox_events_job(publisher: EventPublisher):
    """
    A job function to be run by the scheduler.

    Simply processes pending outbox events. (Not ideal for production use. Just a demo.)

    TODO: more sophisticated scheduling, backoff, batching, exception handling, etc.
    """
    logger.info("Running outbox processor job...")

    async with AsyncTransaction() as session:
        try:
            repo = OutboxRepository()

            events_to_process = await repo.get_and_lock_pending_events(session, limit=10)

            if not events_to_process:
                logger.info("No pending outbox events found.")
                return

            logger.info(f"Found {len(events_to_process)} events to process.")

            # Mark as processing
            for event in events_to_process:
                event.status = EventStatus.PROCESSING
            await session.commit()

            # Process each event
            for event in events_to_process:
                try:
                    await publisher(
                        event.event_type,
                        DomainEvent(
                            id=event.id,
                            source=f"/{event.aggregate_type.lower()}/outbox",
                            type=event.event_type,
                            data=event.payload,
                            meta={
                                "aggregate_type": event.aggregate_type,
                                "aggregate_id": event.aggregate_id,
                            },
                        ),
                    )
                    event.status = EventStatus.PUBLISHED
                    event.processed_at = datetime.datetime.now(UTC)
                except Exception as e:
                    logger.error(f"Failed to process event {event.id}: {e}")
                    event.status = EventStatus.FAILED
                    event.retry_count += 1

            session.add_all(events_to_process)
            await session.commit()
            logger.info("Outbox processor job finished.")

        except Exception as e:
            logger.error(f"Error during outbox processing job: {e}")
            await session.rollback()


async def resolve_zombie_events():
    """
    Resolves zombie events that have been stuck in PROCESSING state for too long.

    These are events that were picked up for processing but never completed,
    likely due to a crash or network issue. This function resets them to PENDING
    so they can be retried, or marks them as FAILED if max retries exceeded (DLQ).
    """
    logger.info("Running zombie event resolver...")

    async with AsyncTransaction() as session:
        try:
            repo = OutboxRepository()

            # Find events stuck in PROCESSING for more than the timeout
            timeout_threshold = datetime.datetime.now(UTC) - datetime.timedelta(seconds=_ZOMBIE_TIMEOUT)

            zombie_events = await repo.get_zombie_events(session, timeout_threshold)

            if not zombie_events:
                logger.info("No zombie events found.")
                return

            logger.warning(f"Found {len(zombie_events)} zombie events.")

            pending_count = 0
            failed_count = 0

            for event in zombie_events:
                event.retry_count += 1

                if event.retry_count >= _ZOMBIE_MAX_RETRIES:
                    # Dead Letter Queue: exceeded max retries
                    event.status = EventStatus.FAILED
                    failed_count += 1
                    logger.error(
                        f"Event {event.id} exceeded max retries ({_ZOMBIE_MAX_RETRIES}). Marking as FAILED (DLQ)."
                    )
                else:
                    # Reset to PENDING for retry
                    event.status = EventStatus.PENDING
                    pending_count += 1

            session.add_all(zombie_events)
            await session.commit()
            logger.info(f"Zombie resolution complete: {pending_count} reset to PENDING, {failed_count} moved to DLQ.")

        except Exception as e:
            logger.error(f"Error during zombie event resolution: {e}")
            await session.rollback()


@asynccontextmanager
async def scheduler_lifespan(
    app: FastAPI,
    publisher: EventPublisher,
    *,
    process_interval_seconds: int = 5,
    zombie_interval_seconds: int = 60 * 10,
):
    """FastAPI lifespan that runs the outbox relay and zombie resolver.

    The consumer injects ``publisher`` (see :class:`EventPublisher`). Wire it into
    an app with ``functools.partial`` so FastAPI still calls it with just ``app``::

        from functools import partial
        from app_prebuilt_outbox.scheduler import scheduler_lifespan, make_faststream_publisher

        # `broker` is any object with an awaitable `publish(message, channel=...)`.
        publisher = make_faststream_publisher(broker)
        app = FastAPI(lifespan=partial(scheduler_lifespan, publisher=publisher))
    """
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        partial(process_outbox_events_job, publisher),
        "interval",
        seconds=process_interval_seconds,
        id="process_outbox",
        max_instances=1,
    )
    scheduler.add_job(
        resolve_zombie_events,
        "interval",
        seconds=zombie_interval_seconds,
        id="resolve_zombies",
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started.")
    yield
    scheduler.shutdown()
    logger.info("Scheduler shut down.")
