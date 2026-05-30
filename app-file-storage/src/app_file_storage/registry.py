import importlib
from typing import ClassVar

from app_file_storage.config import FileProviderType
from app_file_storage.interface import FileStorageClient


class FileStorageRegistry:
    """Registry for file storage providers."""

    _PROVIDER_MODULES: ClassVar[dict[FileProviderType, str]] = {
        FileProviderType.LOCAL: "app_file_storage.providers.local",
        FileProviderType.S3: "app_file_storage.providers.s3",
    }

    _PROVIDER_CLASSES: ClassVar[dict[FileProviderType, str]] = {
        FileProviderType.LOCAL: "LocalStorageProvider",
        FileProviderType.S3: "S3StorageProvider",
    }

    @classmethod
    def get_provider_class(cls, provider: FileProviderType | str) -> type[FileStorageClient]:
        try:
            provider_enum = FileProviderType(provider)
        except ValueError as exc:
            raise ValueError(f"Unsupported file storage client: {provider}") from exc

        if provider_enum not in cls._PROVIDER_MODULES:
            raise ValueError(f"Unsupported file storage client: {provider_enum}")

        module_path = cls._PROVIDER_MODULES[provider_enum]
        class_name = cls._PROVIDER_CLASSES[provider_enum]

        module = importlib.import_module(module_path)
        return getattr(module, class_name)

    @classmethod
    async def create_client(cls, provider: FileProviderType | str) -> FileStorageClient:
        provider_class = cls.get_provider_class(provider)
        return await provider_class.from_env()

    @classmethod
    def list_providers(cls) -> list[str]:
        return [p.value for p in FileProviderType if p != FileProviderType.NONE]
