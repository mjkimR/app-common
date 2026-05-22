from unittest.mock import MagicMock, patch

import pytest
from app_base.adapter.event_broker.factory import EventBrokerFactory
from app_base.config.event_broker import (
    EventBrokerSettings,
    RabbitMQBrokerSettings,
    RedisBrokerSettings,
)


@pytest.fixture
def mock_none_settings():
    mock_settings = MagicMock(spec=EventBrokerSettings)
    mock_settings.provider = "none"
    mock_settings.config = MagicMock()
    return mock_settings


@pytest.fixture
def mock_in_memory_settings():
    mock_settings = MagicMock(spec=EventBrokerSettings)
    mock_settings.provider = "in_memory"
    mock_settings.config = MagicMock()
    return mock_settings


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


@pytest.fixture
def mock_unsupported_settings():
    mock_settings = MagicMock(spec=EventBrokerSettings)
    mock_settings.provider = "unsupported"
    mock_settings.config = MagicMock()
    return mock_settings


def test_create_none_provider(mock_none_settings):
    broker = EventBrokerFactory.create(mock_none_settings)
    assert broker is None


def test_create_in_memory_provider(mock_in_memory_settings):
    with patch("faststream.redis.RedisBroker") as mock_redis_broker:
        mock_broker_instance = MagicMock()
        mock_redis_broker.return_value = mock_broker_instance

        broker = EventBrokerFactory.create(mock_in_memory_settings)

        mock_redis_broker.assert_called_once_with()
        assert broker == mock_broker_instance


def test_create_rabbitmq_provider(mock_rabbitmq_settings):
    with patch("faststream.rabbit.RabbitBroker") as mock_rabbit_broker:
        mock_broker_instance = MagicMock()
        mock_rabbit_broker.return_value = mock_broker_instance

        broker = EventBrokerFactory.create(mock_rabbitmq_settings)

        mock_rabbit_broker.assert_called_once_with(url=mock_rabbitmq_settings.config.connection_url)
        assert broker == mock_broker_instance


def test_create_rabbitmq_provider_wrong_config(mock_rabbitmq_settings):
    mock_rabbitmq_settings.config = MagicMock()  # Wrong config type (not RabbitMQBrokerSettings)
    with pytest.raises(TypeError, match=r"Expected RabbitMQBrokerSettings for rabbitmq provider"):
        EventBrokerFactory.create(mock_rabbitmq_settings)


def test_create_redis_provider(mock_redis_settings):
    with patch("faststream.redis.RedisBroker") as mock_redis_broker:
        mock_broker_instance = MagicMock()
        mock_redis_broker.return_value = mock_broker_instance

        broker = EventBrokerFactory.create(mock_redis_settings)

        mock_redis_broker.assert_called_once_with(url=mock_redis_settings.config.connection_url)
        assert broker == mock_broker_instance


def test_create_redis_provider_wrong_config(mock_redis_settings):
    mock_redis_settings.config = MagicMock()  # Wrong config type (not RedisBrokerSettings)
    with pytest.raises(TypeError, match=r"Expected RedisBrokerSettings for redis provider"):
        EventBrokerFactory.create(mock_redis_settings)


def test_create_unsupported_provider(mock_unsupported_settings):
    with pytest.raises(ValueError, match=r"Unknown provider: unsupported"):
        EventBrokerFactory.create(mock_unsupported_settings)
