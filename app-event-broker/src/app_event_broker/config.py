import functools
import os
from typing import Literal

from app_layer_base.config_util import get_env_file_path
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class BrokerProviderConfigs(BaseSettings):
    pass


BrokerProviderType = Literal["none", "in_memory", "rabbitmq", "redis"]


class NoneBrokerSettings(BrokerProviderConfigs):
    pass


class InMemoryBrokerSettings(BrokerProviderConfigs):
    """Settings for in-memory broker (development/testing).

    Using TestRedisBroker (from faststream.redis import TestRedisBroker) as a simple in-memory broker.
    """

    model_config = SettingsConfigDict(env_prefix="EVENT_BROKER_IN_MEMORY_")


class RabbitMQBrokerSettings(BrokerProviderConfigs):
    """Settings for RabbitMQ broker."""

    url: str = Field(default="localhost", description="RabbitMQ host address")
    port: int = Field(default=5672, description="RabbitMQ AMQP port")
    exchange: str = Field(default="events", description="Default exchange name for publishing messages")
    username: str | None = Field(default=None, description="Username for RabbitMQ authentication")
    password: SecretStr | None = Field(default=None, description="Password for RabbitMQ authentication")

    model_config = SettingsConfigDict(env_prefix="EVENT_BROKER_RABBITMQ_")

    @property
    def connection_url(self) -> str:
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password.get_secret_value()}@"
        return f"amqp://{auth}{self.url}:{self.port}/"


class RedisBrokerSettings(BrokerProviderConfigs):
    """Settings for Redis broker."""

    url: str = Field(default="localhost", description="Redis host address")
    port: int = Field(default=6379, description="Redis port")
    username: str | None = Field(default=None, description="Username for Redis ACL authentication (Redis 6+)")
    password: SecretStr | None = Field(default=None, description="Password for Redis authentication")

    model_config = SettingsConfigDict(env_prefix="EVENT_BROKER_REDIS_")

    @property
    def connection_url(self) -> str:
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password.get_secret_value()}@"
        return f"redis://{auth}{self.url}:{self.port}"


class EventBrokerSettings[TBrokerProviderConfigs: BrokerProviderConfigs](BaseSettings):
    """
    Main settings for event broker.
    Reads from environment variables.
    """

    provider: str = Field(
        default="in_memory",
        alias="EVENT_BROKER_PROVIDER",
        description="Event broker backend to use: none | in_memory | rabbitmq | redis",
    )

    # Nested settings for provider
    config: TBrokerProviderConfigs
    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_nested_delimiter="__",
        validate_assignment=True,
        extra="ignore",
    )

    @classmethod
    def _get_config_class(cls, provider: str) -> type[BrokerProviderConfigs]:
        """Get the appropriate config class for the provider."""
        config_map = {
            "none": NoneBrokerSettings,
            "in_memory": InMemoryBrokerSettings,
            "rabbitmq": RabbitMQBrokerSettings,
            "redis": RedisBrokerSettings,
        }
        return config_map.get(provider, NoneBrokerSettings)

    @model_validator(mode="before")
    @classmethod
    def check_provider_requirements(cls, data: dict) -> dict:
        provider = data.get("provider", "none") or os.getenv("EVENT_BROKER_PROVIDER", "none")
        data["provider"] = provider
        config_class = cls._get_config_class(provider)
        data["config"] = config_class(**{})
        return data


@functools.lru_cache
def get_event_broker_settings() -> EventBrokerSettings:
    """Returns a cached instance of the event broker settings."""
    return EventBrokerSettings(**{})
