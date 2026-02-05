from typing import Any, Optional

from app_base.adapter.event_broker.factory import EventBrokerFactory
from app_base.config import get_event_broker_settings
from app_base.config.event_broker import EventBrokerSettings
from app_base.core.log import logger

_event_broker: Optional[Any] = None


def set_event_broker(event_broker: Any) -> None:
    """Set the global event broker event_broker instance."""
    global _event_broker
    if _event_broker is not None:
        raise RuntimeError("Event broker event_broker is already initialized.")
    _event_broker = event_broker


def get_event_broker() -> Any:
    """Get the global event broker event_broker instance."""
    if _event_broker is None:
        setup_event_broker(settings=get_event_broker_settings())
    return _event_broker


def setup_event_broker(settings: EventBrokerSettings) -> None:
    """Setup the global event broker event_broker instance."""
    if _event_broker is not None:
        logger.info("Event broker event_broker is already initialized.")
        return

    logger.info(f"Initializing event broker event_broker: {settings.provider}")
    event_broker = EventBrokerFactory.create(settings=settings)
    set_event_broker(event_broker)
    logger.info("Event broker event_broker initialized successfully.")


async def close_event_broker() -> None:
    """Close the global event broker event_broker instance."""
    global _event_broker
    if _event_broker:
        await _event_broker.close()
        _event_broker = None
