from threading import RLock
from typing import Any

from loguru import logger

from app_event_broker.config import EventBrokerSettings, get_event_broker_settings
from app_event_broker.factory import EventBrokerFactory

_event_broker: Any | None = None
_event_broker_lock = RLock()


def set_event_broker(event_broker: Any) -> None:
    """Set the global event broker event_broker instance."""
    global _event_broker
    with _event_broker_lock:
        if _event_broker is not None:
            raise RuntimeError("Event broker event_broker is already initialized.")
        _event_broker = event_broker


def get_event_broker() -> Any:
    """Get the global event broker event_broker instance."""
    global _event_broker
    if _event_broker is None:
        with _event_broker_lock:
            if _event_broker is None:
                setup_event_broker(settings=get_event_broker_settings())
    return _event_broker


def setup_event_broker(settings: EventBrokerSettings) -> None:
    """Setup the global event broker event_broker instance."""
    global _event_broker
    if _event_broker is not None:
        logger.info("Event broker event_broker is already initialized.")
        return

    with _event_broker_lock:
        if _event_broker is not None:
            logger.info("Event broker event_broker is already initialized.")
            return
        logger.info(f"Initializing event broker event_broker: {settings.provider}")
        event_broker = EventBrokerFactory.create(settings=settings)
        _event_broker = event_broker
        logger.info("Event broker event_broker initialized successfully.")


async def close_event_broker() -> None:
    """Close the global event broker event_broker instance."""
    global _event_broker
    with _event_broker_lock:
        broker = _event_broker
        _event_broker = None
    if broker:
        await broker.close()
        logger.info("Global event broker event_broker closed.")
