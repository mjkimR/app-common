from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app_base.adapter.event_broker.instance import (
    close_event_broker,
    get_event_broker,
    set_event_broker,
    setup_event_broker,
)
from app_base.config.event_broker import EventBrokerSettings


@pytest.fixture(autouse=True)
def reset_global_event_broker():
    """Reset the global _event_broker before each test."""
    import app_base.adapter.event_broker.instance as event_broker_instance

    original_broker = event_broker_instance._event_broker
    yield
    event_broker_instance._event_broker = original_broker


@pytest.fixture
def mock_broker():
    broker = AsyncMock()
    return broker


def test_set_event_broker(mock_broker):
    set_event_broker(mock_broker)

    import app_base.adapter.event_broker.instance as event_broker_instance

    assert event_broker_instance._event_broker == mock_broker


def test_set_event_broker_already_initialized(mock_broker):
    set_event_broker(mock_broker)
    with pytest.raises(RuntimeError, match="Event broker event_broker is already initialized."):
        set_event_broker(mock_broker)


def test_get_event_broker_not_initialized():
    with (
        patch("app_base.adapter.event_broker.instance.get_event_broker_settings") as mock_get_settings,
        patch("app_base.adapter.event_broker.instance.setup_event_broker") as mock_setup,
    ):
        mock_settings = MagicMock(spec=EventBrokerSettings)
        mock_get_settings.return_value = mock_settings

        get_event_broker()

        mock_setup.assert_called_once_with(settings=mock_settings)


def test_get_event_broker_initialized(mock_broker):
    set_event_broker(mock_broker)
    result = get_event_broker()
    assert result == mock_broker


def test_setup_event_broker_initializes(mock_broker):
    mock_settings = MagicMock(spec=EventBrokerSettings)
    mock_settings.provider = "none"

    with patch(
        "app_base.adapter.event_broker.instance.EventBrokerFactory.create",
        return_value=mock_broker,
    ) as mock_create:
        setup_event_broker(settings=mock_settings)
        mock_create.assert_called_once_with(settings=mock_settings)

    import app_base.adapter.event_broker.instance as event_broker_instance

    assert event_broker_instance._event_broker == mock_broker


def test_setup_event_broker_already_initialized(mock_broker):
    set_event_broker(mock_broker)
    mock_settings = MagicMock(spec=EventBrokerSettings)

    with patch("app_base.adapter.event_broker.instance.EventBrokerFactory.create") as mock_create:
        setup_event_broker(settings=mock_settings)
        mock_create.assert_not_called()


async def test_close_event_broker(mock_broker):
    set_event_broker(mock_broker)
    await close_event_broker()

    import app_base.adapter.event_broker.instance as event_broker_instance

    assert event_broker_instance._event_broker is None
    mock_broker.close.assert_called_once()


async def test_close_event_broker_not_initialized():
    # Should not raise an error if broker is not initialized
    await close_event_broker()

    import app_base.adapter.event_broker.instance as event_broker_instance

    assert event_broker_instance._event_broker is None
