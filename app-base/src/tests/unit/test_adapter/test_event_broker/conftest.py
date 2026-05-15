from unittest.mock import MagicMock

import pytest
from app_base.config.event_broker import (
    EventBrokerSettings,
    RabbitMQBrokerSettings,
    RedisBrokerSettings,
)


@pytest.fixture
def mock_rabbitmq_settings():
    mock_settings = MagicMock(spec=EventBrokerSettings)
    mock_settings.provider = "rabbitmq"
    mock_settings.config = RabbitMQBrokerSettings()
    return mock_settings


@pytest.fixture
def mock_redis_settings():
    mock_settings = MagicMock(spec=EventBrokerSettings)
    mock_settings.provider = "redis"
    mock_settings.config = RedisBrokerSettings()
    return mock_settings
