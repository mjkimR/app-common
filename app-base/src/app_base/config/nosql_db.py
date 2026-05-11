import functools
import os
from typing import Generic, Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import TypeVar

from app_base.config.util import get_env_file_path

NoSQLDBProviderType = Literal["none", "firestore", "mongodb"]


class NoSQLDBProviderConfigs(BaseSettings):
    pass


TNoSQLDBProviderConfigs = TypeVar("TNoSQLDBProviderConfigs", bound=NoSQLDBProviderConfigs)


class NoneNoSQLDBSettings(NoSQLDBProviderConfigs):
    pass


class FirestoreSettings(NoSQLDBProviderConfigs):
    project_id: str = Field(default="dummy-project")
    credentials_path: str | None = Field(default=None)
    database_id: str = Field(default="(default)")
    model_config = SettingsConfigDict(env_prefix="NOSQL_DB_FIRESTORE_")


class MongoDBSettings(NoSQLDBProviderConfigs):
    url: str = Field(default="mongodb://localhost:27017")
    database: str = Field(default="app")
    model_config = SettingsConfigDict(env_prefix="NOSQL_DB_MONGODB_")


class NoSQLDBSettings(BaseSettings, Generic[TNoSQLDBProviderConfigs]):
    provider: NoSQLDBProviderType = Field(default="none", alias="NOSQL_DB_PROVIDER")
    config: TNoSQLDBProviderConfigs
    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_nested_delimiter="__",
        validate_assignment=True,
        extra="ignore",
    )

    @classmethod
    def _get_config_class(cls, provider: str) -> type[NoSQLDBProviderConfigs]:
        """Get the appropriate config class for the provider."""
        config_map = {
            "none": NoneNoSQLDBSettings,
            "firestore": FirestoreSettings,
            "mongodb": MongoDBSettings,
        }
        return config_map.get(provider, NoneNoSQLDBSettings)

    @model_validator(mode="before")
    @classmethod
    def check_provider_requirements(cls, data: dict) -> dict:
        provider = data.get("provider", "none") or os.getenv("NOSQL_DB_PROVIDER", "none")
        data["provider"] = provider
        config_class = cls._get_config_class(provider)
        data["config"] = config_class(**{})
        return data


@functools.lru_cache
def get_nosql_db_settings() -> NoSQLDBSettings:
    return NoSQLDBSettings(**{})
