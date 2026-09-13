import langchain_core.vectorstores
from app_error import Actor, AppError, Retry
from loguru import logger

from app_vector_store.config import VectorDBProviderType, VectorDBSettings
from app_vector_store.factory import VectorStoreFactory
from app_vector_store.interface import VectorStoreProvider
from app_vector_store.registry import VectorStoreRegistry


class VectorStoreNotInitializedError(AppError, RuntimeError):
    code = "VECTOR_STORE_NOT_INITIALIZED"
    actor = Actor.DEVELOPER
    retry = Retry.AFTER_FIX

    def __init__(self) -> None:
        super().__init__(
            "Vector Store provider is not initialized. Check lifespan.",
            target_files=["app/main.py"],
            fix="from app_vector_store.lifespan import register_vector_store_lifespan; register_vector_store_lifespan(app)",
            what_to_report="Vector store provider accessed before initialization in lifespan.",
        )


class VectorStoreAlreadyInitializedError(AppError, RuntimeError):
    code = "VECTOR_STORE_ALREADY_INITIALIZED"
    actor = Actor.DEVELOPER
    retry = Retry.UNSAFE

    def __init__(self) -> None:
        super().__init__(
            "Vector Store provider is already initialized.",
            what_to_report="Vector store provider initialization was called more than once.",
        )


_vector_store_provider: VectorStoreProvider | None = None


def set_vector_store_provider(provider: VectorStoreProvider) -> None:
    """Set the global vector store provider instance."""
    global _vector_store_provider
    if _vector_store_provider is not None:
        raise VectorStoreAlreadyInitializedError()
    _vector_store_provider = provider


def get_vector_store_provider() -> VectorStoreProvider:
    """Get the global vector store provider instance."""
    global _vector_store_provider
    if _vector_store_provider is None:
        raise VectorStoreNotInitializedError()
    return _vector_store_provider


def get_vector_store_factory() -> VectorStoreFactory:
    """Get the global vector store factory instance."""
    return VectorStoreFactory(get_vector_store_provider())


async def get_vector_store(collection_name: str, model_name: str) -> langchain_core.vectorstores.VectorStore:
    """Get a LangChain VectorStore instance."""
    factory = get_vector_store_factory()
    return await factory.get_vector_store(collection_name, model_name)


async def setup_vector_store_provider(settings: VectorDBSettings) -> None:
    """Setup the global vector store provider instance."""
    global _vector_store_provider
    if _vector_store_provider is not None:
        logger.info("Vector Store provider is already initialized.")
        return  # Already initialized

    if settings.provider == VectorDBProviderType.NONE:
        logger.info("Vector Store provider is set to 'none'. Skipping initialization.")
        return

    logger.info(f"Initializing vector store provider of provider: {settings.provider}")
    provider_cls = VectorStoreRegistry.get_provider_cls(settings.provider)
    provider = provider_cls.from_env()
    _vector_store_provider = provider
    logger.info("Vector Store provider initialized successfully.")


async def close_vector_store() -> None:
    """Close the global vector store provider instance."""
    global _vector_store_provider
    provider = _vector_store_provider
    _vector_store_provider = None
    if provider:
        provider.close()
        logger.info("Global vector store provider closed.")
