from .instance import get_storage_client
from .lifespan import lifespan_file_storage
from .interface import FileStorageClient

__all__ = [
    "FileStorageClient",
    "get_storage_client",
    "lifespan_file_storage",
]
