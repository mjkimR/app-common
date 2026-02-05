from contextlib import asynccontextmanager

from fastapi import FastAPI

from app_base.adapter.event_broker.instance import close_event_broker, setup_event_broker
from app_base.config import (
    EventBrokerSettings,
    get_event_broker_settings,
)


@asynccontextmanager
async def lifespan_event_broker(app: FastAPI, settings: EventBrokerSettings | None = None):
    """Lifespan context manager to initialize and cleanup the event broker dispatcher."""
    settings = get_event_broker_settings()
    setup_event_broker(settings=settings)

    yield

    await close_event_broker()
