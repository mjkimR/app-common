import datetime
import logging
from contextlib import asynccontextmanager

from app_base.adapter.event_broker.instance import get_event_broker
from app_base.base.schemas.event import DomainEvent
from app_base.core.database.transaction import AsyncTransaction
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from .models import EventStatus
from .repos import OutboxRepository

logger = logging.getLogger(__name__)
_ZOMBIE_MAX_RETRIES = 3
_ZOMBIE_TIMEOUT = 60 * 60  # 1 hour


async def dispatch_event(event_type: str, event: DomainEvent) -> None:
    """Dispatch event to message broker."""
    broker = get_event_broker()
    if broker is None:
        logger.warning("Event broker is not configured. Skipping event dispatch.")
        return

    # FastStream publish: channel name based on event_type
    channel = f"events.{event_type.lower().replace('_', '.')}"
    message = event.to_message()

    await broker.publish(message, channel=channel)
    logger.debug(f"Event dispatched: {event_type} -> {channel}")


async def process_outbox_events_job():
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
                    await dispatch_event(
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
                    event.processed_at = datetime.datetime.now(datetime.timezone.utc)
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
            timeout_threshold = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(
                seconds=_ZOMBIE_TIMEOUT
            )

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
async def scheduler_lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        process_outbox_events_job,
        "interval",
        seconds=5,
        id="process_outbox",
        max_instances=1,
    )
    scheduler.add_job(
        resolve_zombie_events,
        "interval",
        seconds=60 * 10,
        id="resolve_zombies",
        max_instances=1,
    )
    scheduler.start()
    logger.info("Scheduler started.")
    yield
    scheduler.shutdown()
    logger.info("Scheduler shut down.")
