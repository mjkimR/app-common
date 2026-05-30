from loguru import logger

from app_nosql_db.config import NoSQLDBProviderType, NoSQLDBSettings
from app_nosql_db.interface import NoSQLDBProvider
from app_nosql_db.registry import NoSQLDBRegistry

_nosql_db_provider: NoSQLDBProvider | None = None


def set_nosql_db_provider(provider: NoSQLDBProvider) -> None:
    """Set the global NoSQL DB provider instance."""
    global _nosql_db_provider
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

    if settings.provider == NoSQLDBProviderType.NONE:
        logger.info("NoSQL DB provider is set to 'none'. Skipping initialization.")
        return

    logger.info(f"Initializing NoSQL DB provider of provider: {settings.provider}")

    provider_cls = NoSQLDBRegistry.get_provider_cls(settings.provider)
    provider = provider_cls.from_env()
    _nosql_db_provider = provider
    logger.info("NoSQL DB provider initialized successfully.")


async def close_nosql_db() -> None:
    """Close the global NoSQL DB provider instance."""
    global _nosql_db_provider
    provider = _nosql_db_provider
    _nosql_db_provider = None
    if provider:
        provider.close()
        logger.info("Global NoSQL DB provider closed.")
