from threading import RLock

from app_base.ai.models.client import AIClient
from app_base.core.log import logger

_ai_client: AIClient | None = None
_ai_client_lock = RLock()


def set_ai_client(client: AIClient) -> None:
    """Set the global AI client instance."""
    global _ai_client
    with _ai_client_lock:
        if _ai_client is not None:
            raise RuntimeError("AI client is already initialized.")
        _ai_client = client


def get_ai_client() -> AIClient:
    """Get the global AI client instance, lazily initializing it with the default catalog."""
    if _ai_client is None:
        setup_ai_client()
    if _ai_client is None:
        raise RuntimeError("AI client is not initialized. Check lifespan.")
    return _ai_client


def setup_ai_client(config_path: str = AIClient.DEFAULT_PATH) -> None:
    """Setup the global AI client instance."""
    global _ai_client
    with _ai_client_lock:
        if _ai_client is not None:
            logger.info("AI client is already initialized.")
            return

        logger.info(f"Initializing AI client with catalog: {config_path}")
        _ai_client = AIClient(config_path=config_path)
        logger.info("AI client initialized successfully.")


def reload_ai_client() -> None:
    """Reload the global AI client instance."""
    with _ai_client_lock:
        client = _ai_client
    if client is None:
        setup_ai_client()
        return
    client.reload()


def close_ai_client() -> None:
    """Close the global AI client instance."""
    global _ai_client
    with _ai_client_lock:
        _ai_client = None
