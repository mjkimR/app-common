import functools
import os
from typing import Generic, Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import TypeVar

from app_base.config.util import get_env_file_path


class FileProviderConfigs(BaseSettings):
    pass


TFileProviderConfigs = TypeVar("TFileProviderConfigs", bound=FileProviderConfigs)
FileProviderType = Literal["none", "local", "s3"]


class NoneFileStorageSettings(FileProviderConfigs):
    pass


class LocalFileStorageSettings(FileProviderConfigs):
    """Settings for when the file storage provider is 'local'."""

    bucket_name: str = Field(
        default="local_storage", description="Root directory name used as the local storage bucket"
    )
    model_config = SettingsConfigDict(env_prefix="FS_LOCAL_")


class S3FileStorageSettings(FileProviderConfigs):
    """Settings for when the file storage provider is 's3'."""

    endpoint_url: str = Field(
        default="http://localhost:9000", description="S3-compatible endpoint URL (e.g. MinIO or AWS S3)"
    )
    access_key: SecretStr = Field(default=SecretStr("minioadmin"), description="S3 access key ID for authentication")
    secret_key: SecretStr = Field(
        default=SecretStr("minioadmin"), description="S3 secret access key for authentication"
    )
    bucket_name: str = Field(default="my-bucket", description="Name of the S3 bucket to use for file storage")
    region_name: str | None = Field(
        default=None, description="AWS region name (required for AWS S3, optional for S3-compatible providers)"
    )

    model_config = SettingsConfigDict(env_prefix="FS_S3_")


class FileStorageSettings(BaseSettings, Generic[TFileProviderConfigs]):
    """
    Main settings for file storage.
    Reads from environment variables.
    """

    provider: str = Field(
        default="none", alias="FS_PROVIDER", description="File storage backend to use: none | local | s3"
    )

    # Nested settings for provider
    config: TFileProviderConfigs
    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_nested_delimiter="__",
        validate_assignment=True,
        extra="ignore",
    )

    @classmethod
    def _get_config_class(cls, provider: str) -> type[FileProviderConfigs]:
        """Get the appropriate config class for the provider."""
        config_map = {
            "none": NoneFileStorageSettings,
            "local": LocalFileStorageSettings,
            "s3": S3FileStorageSettings,
        }
        return config_map.get(provider, NoneFileStorageSettings)

    @model_validator(mode="before")
    @classmethod
    def check_provider_requirements(cls, data: dict) -> dict:
        provider = data.get("provider", "none") or os.getenv("FS_PROVIDER", "none")
        data["provider"] = provider
        config_class = cls._get_config_class(provider)
        data["config"] = config_class(**{})
        return data


@functools.lru_cache
def get_file_storage_settings() -> FileStorageSettings:
    """Returns a cached instance of the file storage settings."""
    return FileStorageSettings(**{})
