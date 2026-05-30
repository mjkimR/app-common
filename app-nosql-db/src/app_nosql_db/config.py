import functools
import os
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

NoSQLDBProviderType = Literal["none", "firestore", "mongodb"]


class NoSQLDBProviderConfigs(BaseSettings):
    pass


class NoneNoSQLDBSettings(NoSQLDBProviderConfigs):
    pass


class FirestoreSettings(NoSQLDBProviderConfigs):
    project_id: str = Field(
        default="dummy-project", description="Google Cloud project ID that owns the Firestore database"
    )
    credentials_path: str | None = Field(
        default=None, description="Path to the Google service account JSON credentials file (uses ADC if not set)"
    )
    database_id: str = Field(default="(default)", description="Firestore database ID to connect to")
    model_config = SettingsConfigDict(env_prefix="NOSQL_DB_FIRESTORE_")


class MongoDBSettings(NoSQLDBProviderConfigs):
    url: str = Field(default="mongodb://localhost:27017", description="MongoDB connection URI")
    database: str = Field(default="app", description="Name of the MongoDB database to use")
    model_config = SettingsConfigDict(env_prefix="NOSQL_DB_MONGODB_")


class NoSQLDBSettings[TNoSQLDBProviderConfigs: NoSQLDBProviderConfigs](BaseSettings):
    provider: NoSQLDBProviderType = Field(
        default="none",
        alias="NOSQL_DB_PROVIDER",
        description="NoSQL database backend to use: none | firestore | mongodb",
    )
    config: TNoSQLDBProviderConfigs
    model_config = SettingsConfigDict(
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
