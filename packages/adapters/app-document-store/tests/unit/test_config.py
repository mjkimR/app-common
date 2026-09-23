import pytest
from app_document_store import FirestoreSettings, create_firestore_client, open_firestore
from app_document_store.config import validate_segment
from pydantic import ValidationError


@pytest.mark.parametrize("value", ["", " ", ".", "..", "a/b", "__reserved__", "한" * 501])
def test_invalid_segments(value):
    with pytest.raises(ValueError):
        validate_segment(value)


def test_settings_are_owned_by_adapter(monkeypatch):
    monkeypatch.setenv("DOCUMENT_STORE_PROJECT_ID", "demo-contract")
    monkeypatch.setenv("DOCUMENT_STORE_NAMESPACE", "autohub")
    monkeypatch.setenv("DOCUMENT_STORE_TIMEOUT", "3")
    settings = FirestoreSettings()
    assert settings.project_id == "demo-contract"
    assert settings.namespace == "autohub"
    assert settings.timeout == 3
    assert settings.database_id == "(default)"
    with pytest.raises(ValidationError):
        FirestoreSettings(timeout=0)


def test_production_rejects_ambient_emulator(monkeypatch):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    with pytest.raises(ValueError, match="Unset"):
        create_firestore_client(FirestoreSettings(project_id="demo-contract", namespace="test"))


@pytest.mark.parametrize("host", [None, "", "http://localhost:8080", "localhost"])
def test_emulator_requires_explicit_endpoint(monkeypatch, host):
    monkeypatch.delenv("FIRESTORE_EMULATOR_HOST", raising=False)
    if host is not None:
        monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", host)
    with pytest.raises(ValueError, match="host:port"):
        create_firestore_client(FirestoreSettings(project_id="demo-contract", namespace="test", mode="emulator"))


async def test_lifespan_closes_initialized_transport_on_error(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, Mock

    import app_document_store.client as module

    close = AsyncMock()
    client = SimpleNamespace(
        _firestore_api_internal=SimpleNamespace(transport=SimpleNamespace(close=close)), close=Mock()
    )
    monkeypatch.setattr(module, "create_firestore_client", lambda settings: client)
    with pytest.raises(RuntimeError, match="application failed"):
        async with open_firestore(FirestoreSettings(project_id="demo-contract", namespace="test")):
            raise RuntimeError("application failed")
    close.assert_awaited_once()
    client.close.assert_called_once()


async def test_unused_emulator_client_needs_no_credentials_or_transport(monkeypatch):
    monkeypatch.setenv("FIRESTORE_EMULATOR_HOST", "localhost:8080")
    settings = FirestoreSettings(project_id="demo-contract", namespace="test", mode="emulator")
    async with open_firestore(settings) as client:
        assert client.project == "demo-contract"
        assert client._firestore_api_internal is None
