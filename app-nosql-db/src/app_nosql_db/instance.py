from threading import RLock

from loguru import logger

from app_nosql_db.config import NoSQLDBSettings
from app_nosql_db.interface import NoSQLDBProvider
from app_nosql_db.registry import get_provider_cls

_nosql_db_provider: NoSQLDBProvider | None = None
_nosql_db_provider_lock = RLock()


def set_nosql_db_provider(provider: NoSQLDBProvider) -> None:
    """Set the global NoSQL DB provider instance."""
    global _nosql_db_provider
    with _nosql_db_provider_lock:
        if _nosql_db_provider is not None:
            raise RuntimeError("NoSQL DB provider is already initialized.")
        _nosql_db_provider = provider


def get_nosql_db_provider() -> NoSQLDBProvider:
    """Get the global NoSQL DB provider instance."""
    global _nosql_db_provider
    if _nosql_db_provider is None:
        raise RuntimeError("NoSQL DB provider is not initialized. Check lifespan.")
    return _nosql_db_provider


async def setup_nosql_db_provider(settings: NoSQLDBSettings) -> None:
    """Setup the global NoSQL DB provider instance."""
    global _nosql_db_provider
    if _nosql_db_provider is not None:
        logger.info("NoSQL DB provider is already initialized.")
        return  # Already initialized

    if settings.provider == "none":
        logger.info("NoSQL DB provider is set to 'none'. Skipping initialization.")
        return

    with _nosql_db_provider_lock:
        if _nosql_db_provider is not None:
            logger.info("NoSQL DB provider is already initialized.")
            return
        logger.info(f"Initializing NoSQL DB provider of provider: {settings.provider}")
        # Import providers to ensure they are registered
        import app_nosql_db.providers  # noqa: F401

        provider_cls = get_provider_cls(settings.provider)
        provider = provider_cls.from_config(settings)
        _nosql_db_provider = provider
        logger.info("NoSQL DB provider initialized successfully.")


async def close_nosql_db() -> None:
    """Close the global NoSQL DB provider instance."""
    global _nosql_db_provider
    with _nosql_db_provider_lock:
        provider = _nosql_db_provider
        _nosql_db_provider = None
    if provider:
        provider.close()
        logger.info("Global NoSQL DB provider closed.")
