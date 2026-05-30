from unittest.mock import MagicMock

import pytest
from app_ai_catalog.models.client import AIClient
from app_ai_catalog.models.instance import (
    close_ai_client,
    get_ai_client,
    reload_ai_client,
    set_ai_client,
    setup_ai_client,
)


@pytest.fixture(autouse=True)
def reset_global_ai_client():
    import app_ai_catalog.models.instance as ai_instance

    original_client = ai_instance._ai_client
    ai_instance._ai_client = None
    yield
    ai_instance._ai_client = original_client


@pytest.fixture
def mock_client():
    return MagicMock(spec=AIClient)


def test_set_ai_client(mock_client):
    set_ai_client(mock_client)

    assert get_ai_client() == mock_client


def test_set_ai_client_already_initialized(mock_client):
    set_ai_client(mock_client)

    with pytest.raises(RuntimeError, match=r"AI client is already initialized\."):
        set_ai_client(MagicMock(spec=AIClient))


def test_get_ai_client_lazily_initializes_default_client(mocker, mock_client):
    mock_ai_client_cls = mocker.patch("app_ai_catalog.models.instance.AIClient", return_value=mock_client)

    assert get_ai_client() == mock_client
    mock_ai_client_cls.assert_called_once_with(config_path=AIClient.DEFAULT_PATH)


def test_setup_ai_client_initializes_client(mocker, mock_client, tmp_path):
    config_path = str(tmp_path / "catalog.yml")
    mock_ai_client_cls = mocker.patch("app_ai_catalog.models.instance.AIClient", return_value=mock_client)

    setup_ai_client(config_path=config_path)

    mock_ai_client_cls.assert_called_once_with(config_path=config_path)
    assert get_ai_client() == mock_client


def test_setup_ai_client_already_initialized(mocker, mock_client, tmp_path):
    set_ai_client(mock_client)
    mock_ai_client_cls = mocker.patch("app_ai_catalog.models.instance.AIClient")

    setup_ai_client(config_path=str(tmp_path / "catalog.yml"))

    mock_ai_client_cls.assert_not_called()
    assert get_ai_client() == mock_client


def test_reload_ai_client_reloads_existing_client(mock_client):
    set_ai_client(mock_client)

    reload_ai_client()

    mock_client.reload.assert_called_once()


def test_reload_ai_client_lazily_initializes_when_missing(mocker, mock_client):
    mock_ai_client_cls = mocker.patch("app_ai_catalog.models.instance.AIClient", return_value=mock_client)

    reload_ai_client()

    mock_ai_client_cls.assert_called_once_with(config_path=AIClient.DEFAULT_PATH)
    mock_client.reload.assert_not_called()


def test_close_ai_client(mock_client):
    set_ai_client(mock_client)

    close_ai_client()

    with (
        pytest.raises(RuntimeError, match=r"AI client is not initialized\. Check lifespan\."),
        pytest.MonkeyPatch.context() as monkeypatch,
    ):
        monkeypatch.setattr("app_ai_catalog.models.instance.setup_ai_client", lambda: None)
        get_ai_client()
