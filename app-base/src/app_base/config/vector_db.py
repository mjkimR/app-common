import functools
import os
from typing import Generic, Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import TypeVar

VectorDBProviderType = Literal["none", "qdrant", "milvus"]


class VectorDBProviderConfigs(BaseSettings):
    pass


TVectorDBProviderConfigs = TypeVar("TVectorDBProviderConfigs", bound=VectorDBProviderConfigs | None)


class QdrantSettings(VectorDBProviderConfigs):
    url: str = Field(default="http://localhost:6333")
    api_key: SecretStr = Field()
    model_config = SettingsConfigDict(env_prefix="VECTOR_DB_QDRANT_")


class MilvusSettings(VectorDBProviderConfigs):
    url: str = Field(default="tcp://localhost:19530")
    api_key: SecretStr = Field()
    model_config = SettingsConfigDict(env_prefix="VECTOR_DB_MILVUS_")


class VectorDBSettings(BaseSettings, Generic[TVectorDBProviderConfigs]):
    provider: VectorDBProviderType = Field(default="qdrant", alias="VECTOR_DB_PROVIDER")
    config: TVectorDBProviderConfigs = Field(default=None)
    model_config = SettingsConfigDict(
        env_nested_delimiter="__",
        validate_assignment=True,
        extra="ignore",
    )

    @model_validator(mode="before")
    @classmethod
    def check_provider_requirements(cls, data: dict) -> dict:
        provider = data.get("provider", "none") or os.getenv("VECTOR_DB_PROVIDER", "none")
        data["provider"] = provider
        if not provider or provider == "none":
            data["config"] = None
        if provider == "qdrant":
            data["config"] = QdrantSettings()  # type: ignore
        elif provider == "milvus":
            data["config"] = MilvusSettings()  # type: ignore
        return data


@functools.lru_cache
def get_vector_db_settings() -> VectorDBSettings:
    return VectorDBSettings()
