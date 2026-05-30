import functools
from enum import StrEnum

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class NoSQLDBProviderType(StrEnum):
    NONE = "none"
    FIRESTORE = "firestore"
    MONGODB = "mongodb"


class NoSQLDBSettings(BaseSettings):
    provider: NoSQLDBProviderType = Field(
        default=NoSQLDBProviderType.NONE,
        alias="NOSQL_DB_PROVIDER",
        description="NoSQL database backend to use: none | firestore | mongodb",
    )
    model_config = SettingsConfigDict(
        extra="ignore",
    )


@functools.lru_cache
def get_nosql_db_settings() -> NoSQLDBSettings:
    return NoSQLDBSettings()
