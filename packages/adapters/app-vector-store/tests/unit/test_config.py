from unittest.mock import AsyncMock, patch

import pytest
from app_vector_store import QdrantSettings, create_qdrant_client, open_qdrant
from pydantic import ValidationError


@pytest.mark.parametrize(
    "values",
    [
        {},
        {"mode": "local"},
        {"mode": "remote"},
        {"mode": "remote", "url": "localhost:6333"},
        {"mode": "local", "path": "data", "url": "http://localhost:6333"},
        {"mode": "memory", "path": "data"},
        {"mode": "memory", "api_key": "secret"},
        {"mode": "local", "path": "data", "api_key": "secret"},
        {"mode": "remote", "url": "http://localhost:6333", "path": "data"},
        {"mode": "memory", "timeout": 0},
    ],
)
def test_invalid_settings(values):
    with pytest.raises(ValidationError):
        QdrantSettings(**values)


def test_environment_and_explicit_precedence(monkeypatch):
    monkeypatch.setenv("VECTOR_DB_MODE", "remote")
    monkeypatch.setenv("VECTOR_DB_URL", "https://environment.example")
    monkeypatch.setenv("VECTOR_DB_API_KEY", "secret")
    settings = QdrantSettings(url="https://explicit.example")
    assert settings.url == "https://explicit.example"
    assert "secret" not in repr(settings)
    with pytest.raises(ValidationError):
        QdrantSettings(mode="local", path="data")


@pytest.mark.parametrize("api_key", [None, "secret"])
def test_remote_connection_configuration(api_key):
    settings = QdrantSettings(mode="remote", url="https://qdrant.example", api_key=api_key, timeout=3)
    with patch("app_vector_store.client.AsyncQdrantClient") as constructor:
        assert create_qdrant_client(settings) is constructor.return_value
        constructor.assert_called_once_with(url="https://qdrant.example", api_key=api_key, timeout=3)


async def test_context_closes_on_failure():
    client = AsyncMock()
    with (
        patch("app_vector_store.client.create_qdrant_client", return_value=client),
        pytest.raises(RuntimeError, match="body failed"),
    ):
        async with open_qdrant(QdrantSettings(mode="memory")):
            raise RuntimeError("body failed")
    client.close.assert_awaited_once()
