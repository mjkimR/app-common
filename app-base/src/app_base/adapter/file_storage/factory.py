from typing import Annotated

from config import FileStorageSettings, get_file_storage_settings
from fastapi.params import Depends

from app_base.adapter.file_storage.interface import FileStorageClient
from app_base.adapter.file_storage.providers import LocalStorageProvider, S3StorageProvider


class FileStorageFactory:
    _providers = {
        "local": LocalStorageProvider,
        "s3": S3StorageProvider,
    }

    @classmethod
    async def create_client(
        cls, config: Annotated[FileStorageSettings, Depends(get_file_storage_settings)]
    ) -> FileStorageClient:
        provider_name = config.provider
        if provider_name not in cls._providers:
            raise ValueError(f"Unsupported file storage client: {provider_name}")

        provider_class: FileStorageClient = cls._providers[provider_name]
        return await provider_class.from_config(config)
