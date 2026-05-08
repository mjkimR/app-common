from typing import Optional

from app_base.adapter.nosql_db.interface import NoSQLDBProvider
from app_base.adapter.nosql_db.registry import get_provider_cls
from app_base.config.nosql_db import NoSQLDBSettings
from app_base.core.log import logger

_nosql_db_provider: Optional[NoSQLDBProvider] = None


def set_nosql_db_provider(provider: NoSQLDBProvider) -> None:
    """Set the global NoSQL DB provider instance."""
    global _nosql_db_provider
    if _nosql_db_provider is not None:
        raise RuntimeError("NoSQL DB provider is already initialized.")
    _nosql_db_provider = provider


def get_nosql_db_provider() -> NoSQLDBProvider:
    """Get the global NoSQL DB provider instance."""
    if _nosql_db_provider is None:
        raise RuntimeError("NoSQL DB provider is not initialized. Check lifespan.")
    return _nosql_db_provider


async def setup_nosql_db_provider(settings: NoSQLDBSettings) -> None:
    """Setup the global NoSQL DB provider instance."""
    if _nosql_db_provider is not None:
        logger.info("NoSQL DB provider is already initialized.")
        return  # Already initialized

    if settings.provider == "none":
        logger.info("NoSQL DB provider is set to 'none'. Skipping initialization.")
        return

    logger.info(f"Initializing NoSQL DB provider of provider: {settings.provider}")
    # Import providers to ensure they are registered
    import app_base.adapter.nosql_db.providers  # noqa: F401

    provider_cls = get_provider_cls(settings.provider)
    provider = provider_cls.from_config(settings)
    set_nosql_db_provider(provider)
    logger.info("NoSQL DB provider initialized successfully.")


async def close_nosql_db() -> None:
    """Close the global NoSQL DB provider instance."""
    global _nosql_db_provider
    if _nosql_db_provider:
        _nosql_db_provider.close()
        _nosql_db_provider = None
