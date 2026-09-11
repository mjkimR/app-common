from typing import Annotated

from fastapi import Depends

from app_file_storage.config import FileProviderType, FileStorageSettings, get_file_storage_settings
from app_file_storage.interface import FileStorageClient
from app_file_storage.registry import FileStorageRegistry


class FileStorageFactory:
    @classmethod
    async def create_client(
        cls, config: Annotated[FileStorageSettings, Depends(get_file_storage_settings)]
    ) -> FileStorageClient:
        if config.provider == FileProviderType.NONE:
            raise ValueError("File storage provider is set to 'none' but a client was requested.")

        return await FileStorageRegistry.create_client(config.provider)
