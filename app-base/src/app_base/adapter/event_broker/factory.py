from typing import Any

from app_base.config.event_broker import (
    EventBrokerSettings,
    RabbitMQBrokerSettings,
    RedisBrokerSettings,
)


class EventBrokerFactory:
    @classmethod
    def create(cls, settings: EventBrokerSettings) -> Any:
        """Create event broker instance."""
        config = settings.config

        if settings.provider == "none":
            return None

        elif settings.provider == "in_memory":
            from faststream.redis import RedisBroker

            # In-memory mode: RedisBroker without URL (wrap with TestRedisBroker in tests)
            return RedisBroker()

        elif settings.provider == "rabbitmq":
            from faststream.rabbit import RabbitBroker

            if not isinstance(config, RabbitMQBrokerSettings):
                raise TypeError("Expected RabbitMQBrokerSettings for rabbitmq provider")
            return RabbitBroker(url=config.connection_url)

        elif settings.provider == "redis":
            from faststream.redis import RedisBroker

            if not isinstance(config, RedisBrokerSettings):
                raise TypeError("Expected RedisBrokerSettings for redis provider")
            return RedisBroker(url=config.connection_url)

        else:
            raise ValueError(f"Unknown provider: {settings.provider}")
