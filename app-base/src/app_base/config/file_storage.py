import functools
import os
from typing import Generic, Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import TypeVar


class FileProviderConfigs(BaseSettings):
    pass


TFileProviderConfigs = TypeVar("TFileProviderConfigs", bound=FileProviderConfigs | None)
FileProviderType = Literal["none", "local", "s3"]


class LocalFileStorageSettings(FileProviderConfigs):
    """Settings for when the file storage provider is 'local'."""

    bucket_name: str = "local_storage"  # This will be the root directory name
    model_config = SettingsConfigDict(env_prefix="FS_LOCAL_")


class S3FileStorageSettings(FileProviderConfigs):
    """Settings for when the file storage provider is 's3'."""

    endpoint_url: str = "http://localhost:9000"
    access_key: SecretStr = Field(default="minioadmin")
    secret_key: SecretStr = Field(default="minioadmin")
    bucket_name: str = "my-bucket"
    region_name: str | None = None

    model_config = SettingsConfigDict(env_prefix="FS_S3_")


class FileStorageSettings(BaseSettings, Generic[TFileProviderConfigs]):
    """
    Main settings for file storage.
    Reads from environment variables.
    """

    provider: str = Field(default="none", alias="FS_PROVIDER")

    # Nested settings for provider
    config: TFileProviderConfigs = Field(default=None)
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        validate_assignment=True,
        extra="ignore",
    )

    @model_validator(mode="before")
    @classmethod
    def check_provider_requirements(cls, data: dict) -> dict:
        provider = data.get("provider", "none") or os.getenv("FS_PROVIDER", "none")
        data["provider"] = provider
        if not provider or provider == "none":
            data["config"] = None
        if provider == "s3":
            data["config"] = S3FileStorageSettings()
        elif provider == "local":
            data["config"] = LocalFileStorageSettings()
        return data


@functools.lru_cache
def get_file_storage_settings() -> FileStorageSettings:
    """Returns a cached instance of the file storage settings."""
    return FileStorageSettings()
