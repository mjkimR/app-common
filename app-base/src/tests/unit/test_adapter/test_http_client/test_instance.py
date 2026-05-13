import sys
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from app_base.adapter.http_client.instance import (
    close_http_client,
    close_http_sync_client,
    get_http_client,
    get_http_sync_client,
    set_http_client,
    set_http_sync_client,
    setup_http_client,
    setup_http_sync_client,
)


@pytest.fixture(autouse=True)
def reset_module_global_http_client():
    try:
        instance_module = sys.modules.get("app_base.adapter.http_client.instance")
        if instance_module:
            instance_module._http_client = None  # type: ignore[reportAttributeAccessIssue]
            instance_module._http_sync_client = None  # type: ignore[reportAttributeAccessIssue]
        yield
        if instance_module:
            instance_module._http_client = None  # type: ignore[reportAttributeAccessIssue]
            instance_module._http_sync_client = None  # type: ignore[reportAttributeAccessIssue]
    except KeyError:
        yield


def test_set_http_client():
    mock_client = MagicMock(spec=httpx.AsyncClient)
    set_http_client(mock_client)
    assert get_http_client() == mock_client


def test_set_http_client_already_initialized():
    mock_client = MagicMock(spec=httpx.AsyncClient)
    set_http_client(mock_client)
    with pytest.raises(RuntimeError, match="HTTP client is already initialized."):
        set_http_client(mock_client)


def test_set_http_sync_client():
    mock_client = MagicMock(spec=httpx.Client)
    set_http_sync_client(mock_client)
    assert get_http_sync_client() == mock_client


def test_set_http_sync_client_already_initialized():
    mock_client = MagicMock(spec=httpx.Client)
    set_http_sync_client(mock_client)
    with pytest.raises(RuntimeError, match="Synchronous HTTP client is already initialized."):
        set_http_sync_client(mock_client)


def test_get_http_client_not_initialized():
    with pytest.raises(RuntimeError, match="HTTP client is not initialized. Check lifespan."):
        get_http_client()


def test_get_http_sync_client_not_initialized():
    with pytest.raises(RuntimeError, match="Synchronous HTTP client is not initialized. Check lifespan."):
        get_http_sync_client()


@pytest.fixture
def mock_http_settings():
    settings = MagicMock()
    settings.TIMEOUT = 10.0
    settings.MAX_CONNECTIONS = 100
    settings.MAX_KEEPALIVE_CONNECTIONS = 20
    settings.KEEPALIVE_EXPIRY = 5.0
    return settings


@pytest.mark.asyncio
@patch("app_base.adapter.http_client.instance.get_http_client_settings")
async def test_setup_http_client(mock_get_settings, mock_http_settings):
    mock_get_settings.return_value = mock_http_settings
    await setup_http_client()

    client = get_http_client()
    assert isinstance(client, httpx.AsyncClient)


@pytest.mark.asyncio
@patch("app_base.adapter.http_client.instance.logger")
async def test_setup_http_client_already_initialized(mock_logger):
    mock_client = MagicMock(spec=httpx.AsyncClient)
    set_http_client(mock_client)

    await setup_http_client()
    mock_logger.info.assert_called_with("HTTP client is already initialized.")


@patch("app_base.adapter.http_client.instance.get_http_client_settings")
def test_setup_http_sync_client(mock_get_settings, mock_http_settings):
    mock_get_settings.return_value = mock_http_settings
    setup_http_sync_client()

    client = get_http_sync_client()
    assert isinstance(client, httpx.Client)


@patch("app_base.adapter.http_client.instance.logger")
def test_setup_http_sync_client_already_initialized(mock_logger):
    mock_client = MagicMock(spec=httpx.Client)
    set_http_sync_client(mock_client)

    setup_http_sync_client()
    mock_logger.info.assert_called_with("Synchronous HTTP client is already initialized.")


@pytest.mark.asyncio
async def test_close_http_client():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    set_http_client(mock_client)

    await close_http_client()

    mock_client.aclose.assert_awaited_once()
    with pytest.raises(RuntimeError, match="HTTP client is not initialized. Check lifespan."):
        get_http_client()


@pytest.mark.asyncio
async def test_close_http_client_not_initialized():
    # Should not raise any error
    await close_http_client()


def test_close_http_sync_client():
    mock_client = MagicMock(spec=httpx.Client)
    set_http_sync_client(mock_client)

    close_http_sync_client()

    mock_client.close.assert_called_once()
    with pytest.raises(RuntimeError, match="Synchronous HTTP client is not initialized. Check lifespan."):
        get_http_sync_client()


def test_close_http_sync_client_not_initialized():
    # Should not raise any error
    close_http_sync_client()
