import httpx

from app_base.config import get_http_client_settings
from app_base.core.log import logger

_http_client: httpx.AsyncClient | None = None
_http_sync_client: httpx.Client | None = None


def set_http_client(client: httpx.AsyncClient) -> None:
    """Set the global HTTP client instance."""
    global _http_client
    if _http_client is not None:
        raise RuntimeError("HTTP client is already initialized.")
    _http_client = client


def set_http_sync_client(client: httpx.Client) -> None:
    """Set the global synchronous HTTP client instance."""
    global _http_sync_client
    if _http_sync_client is not None:
        raise RuntimeError("Synchronous HTTP client is already initialized.")
    _http_sync_client = client


def get_http_client() -> httpx.AsyncClient:
    """Get the global HTTP client instance."""
    if _http_client is None:
        raise RuntimeError("HTTP client is not initialized. Check lifespan.")
    return _http_client


def get_http_sync_client() -> httpx.Client:
    """Get the global synchronous HTTP client instance."""
    if _http_sync_client is None:
        raise RuntimeError("Synchronous HTTP client is not initialized. Check lifespan.")
    return _http_sync_client


async def setup_http_client() -> None:
    """Setup the global HTTP client instance."""
    global _http_client
    if _http_client is not None:
        logger.info("HTTP client is already initialized.")
        return

    logger.info("Initializing global httpx AsyncClient")
    settings = get_http_client_settings()
    client = httpx.AsyncClient(
        timeout=httpx.Timeout(settings.TIMEOUT),
        limits=httpx.Limits(
            max_connections=settings.MAX_CONNECTIONS,
            max_keepalive_connections=settings.MAX_KEEPALIVE_CONNECTIONS,
            keepalive_expiry=settings.KEEPALIVE_EXPIRY,
        ),
    )
    set_http_client(client)
    logger.info("HTTP client initialized successfully.")


def setup_http_sync_client() -> None:
    """Setup the global synchronous HTTP client instance."""
    global _http_sync_client
    if _http_sync_client is not None:
        logger.info("Synchronous HTTP client is already initialized.")
        return

    logger.info("Initializing global httpx Client (Sync)")
    settings = get_http_client_settings()
    client = httpx.Client(
        timeout=httpx.Timeout(settings.TIMEOUT),
        limits=httpx.Limits(
            max_connections=settings.MAX_CONNECTIONS,
            max_keepalive_connections=settings.MAX_KEEPALIVE_CONNECTIONS,
            keepalive_expiry=settings.KEEPALIVE_EXPIRY,
        ),
    )
    set_http_sync_client(client)
    logger.info("Synchronous HTTP client initialized successfully.")


async def close_http_client() -> None:
    """Close the global HTTP client instance."""
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
        logger.info("Global httpx AsyncClient closed.")


def close_http_sync_client() -> None:
    """Close the global synchronous HTTP client instance."""
    global _http_sync_client
    if _http_sync_client:
        _http_sync_client.close()
        _http_sync_client = None
        logger.info("Global httpx Client (Sync) closed.")
