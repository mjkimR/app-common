from typing import Optional

from app_base.adapter.file_storage.factory import FileStorageFactory
from app_base.adapter.file_storage.interface import FileStorageClient
from app_base.config import FileStorageSettings
from app_base.core.log import logger

_file_storage_client: Optional[FileStorageClient] = None


def set_file_storage_client(client: FileStorageClient) -> None:
    """Set the global file storage client instance."""
    global _file_storage_client
    if _file_storage_client is not None:
        raise RuntimeError("File storage client is already initialized.")
    _file_storage_client = client


def get_storage_client() -> FileStorageClient:
    """Get the global file storage client instance."""
    if _file_storage_client is None:
        raise RuntimeError("File storage client is not initialized. Check lifespan.")
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
