import functools
import os
from typing import Generic, Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import TypeVar

from app_base.config.util import get_env_file_path

VectorDBProviderType = Literal["none", "qdrant", "milvus"]


class VectorDBProviderConfigs(BaseSettings):
    pass


TVectorDBProviderConfigs = TypeVar("TVectorDBProviderConfigs", bound=VectorDBProviderConfigs)


class NoneVectorDBSettings(VectorDBProviderConfigs):
    pass


class QdrantSettings(VectorDBProviderConfigs):
    url: str = Field(default="http://localhost:6333", description="Qdrant server URL")
    api_key: SecretStr = Field(description="API key for Qdrant authentication")
    model_config = SettingsConfigDict(env_prefix="VECTOR_DB_QDRANT_")


class MilvusSettings(VectorDBProviderConfigs):
    url: str = Field(default="tcp://localhost:19530", description="Milvus server address in tcp://host:port format")
    api_key: SecretStr = Field(description="API key for Milvus authentication (required for Zilliz Cloud)")
    model_config = SettingsConfigDict(env_prefix="VECTOR_DB_MILVUS_")


class VectorDBSettings(BaseSettings, Generic[TVectorDBProviderConfigs]):
    provider: VectorDBProviderType = Field(
        default="qdrant",
        alias="VECTOR_DB_PROVIDER",
        description="Vector database backend to use: none | qdrant | milvus",
    )
    config: TVectorDBProviderConfigs
    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_nested_delimiter="__",
        validate_assignment=True,
        extra="ignore",
    )

    @classmethod
    def _get_config_class(cls, provider: str) -> type[VectorDBProviderConfigs]:
        """Get the appropriate config class for the provider."""
        config_map = {
            "none": NoneVectorDBSettings,
            "qdrant": QdrantSettings,
            "milvus": MilvusSettings,
        }
        return config_map.get(provider, NoneVectorDBSettings)

    @model_validator(mode="before")
    @classmethod
    def check_provider_requirements(cls, data: dict) -> dict:
        provider = data.get("provider", "none") or os.getenv("VECTOR_DB_PROVIDER", "none")
        data["provider"] = provider
        config_class = cls._get_config_class(provider)
        data["config"] = config_class(**{})
        return data


@functools.lru_cache
def get_vector_db_settings() -> VectorDBSettings:
    return VectorDBSettings(**{})
