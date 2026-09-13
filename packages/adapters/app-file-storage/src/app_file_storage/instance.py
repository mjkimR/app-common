from app_error import Actor, AppError, Retry
from loguru import logger

from app_file_storage.config import FileStorageSettings
from app_file_storage.factory import FileStorageFactory
from app_file_storage.interface import FileStorageClient


class FileStorageNotInitializedError(AppError, RuntimeError):
    code = "FILE_STORAGE_NOT_INITIALIZED"
    actor = Actor.DEVELOPER
    retry = Retry.AFTER_FIX

    def __init__(self) -> None:
        super().__init__(
            "File storage client is not initialized. Check lifespan.",
            target_files=["app/main.py"],
            fix="from app_file_storage.lifespan import register_file_storage_lifespan; register_file_storage_lifespan(app)",
            what_to_report="File storage client accessed before initialization in lifespan.",
        )


class FileStorageAlreadyInitializedError(AppError, RuntimeError):
    code = "FILE_STORAGE_ALREADY_INITIALIZED"
    actor = Actor.DEVELOPER
    retry = Retry.UNSAFE

    def __init__(self) -> None:
        super().__init__(
            "File storage client is already initialized.",
            what_to_report="File storage client initialization was called more than once.",
        )


_file_storage_client: FileStorageClient | None = None


def set_file_storage_client(client: FileStorageClient) -> None:
    """Set the global file storage client instance."""
    global _file_storage_client
    if _file_storage_client is not None:
        raise FileStorageAlreadyInitializedError()
    _file_storage_client = client


def get_storage_client() -> FileStorageClient:
    """Get the global file storage client instance."""
    if _file_storage_client is None:
        raise FileStorageNotInitializedError()
    return _file_storage_client


async def setup_storage_client(settings: FileStorageSettings) -> None:
    """Setup the global file storage client instance."""
    if _file_storage_client is not None:
        logger.info("File storage client is already initialized.")
        return  # Already initialized
    logger.info(f"Initializing file storage client of provider: {settings.provider}")
    client = await FileStorageFactory.create_client(config=settings)
    set_file_storage_client(client)
    logger.info("File storage client initialized successfully.")


async def close_storage_client() -> None:
    """Close the global file storage client instance."""
    global _file_storage_client
    if _file_storage_client:
        await _file_storage_client.close()
        _file_storage_client = None
