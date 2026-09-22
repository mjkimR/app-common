from datetime import UTC, datetime, timedelta, timezone
from typing import Annotated

import pytest
from app_layer_base.base.exceptions.handler import set_exception_handler
from app_layer_base.utils.time_util import get_current_utc_time
from app_prebuilt_auth.api_key.api import api_keys_router
from app_prebuilt_auth.api_key.config import ApiKeySettings, get_api_key_settings
from app_prebuilt_auth.api_key.database import get_api_key_session_maker
from app_prebuilt_auth.api_key.deps import get_machine_principal
from app_prebuilt_auth.api_key.models import MachineKey
from app_prebuilt_auth.api_key.schemas import MachinePrincipal
from app_prebuilt_auth.api_key.usecases import get_machine_scopes
from fastapi import Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

pytestmark = pytest.mark.real_commit
ROOT = "root-test-credential-at-least-32-characters"
ADMIN = {"X-Root-API-Key": ROOT}


@pytest.fixture
async def http(session, session_maker):
    app = FastAPI()
    app.include_router(api_keys_router, prefix="/api/v1")
    set_exception_handler(app)
    app.dependency_overrides[get_api_key_settings] = lambda: ApiKeySettings(root_key=ROOT)
    app.dependency_overrides[get_api_key_session_maker] = lambda: session_maker
    app.dependency_overrides[get_machine_scopes] = lambda: frozenset({"test:run"})

    @app.get("/run")
    async def run(machine: Annotated[MachinePrincipal, Depends(get_machine_principal)]):
        return machine

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, app


async def provision(client):
    response = await client.post("/api/v1/machines", headers=ADMIN, json={"name": "scheduler", "scopes": ["test:run"]})
    assert response.status_code == 201, response.text
    machine = response.json()
    response = await client.post(f"/api/v1/machines/{machine['id']}/keys", headers=ADMIN, json={"label": "deploy"})
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    return machine, response.json()


async def test_lifecycle_rotation_and_secret_storage(http, session_maker):
    client, _ = http
    machine, first = await provision(client)
    path = f"/api/v1/machines/{machine['id']}/keys"
    second = (await client.post(path, headers=ADMIN, json={"label": "replacement"})).json()
    assert first["key"] != second["key"]
    for issued in (first, second):
        response = await client.get("/run", headers={"X-API-Key": issued["key"]})
        assert response.status_code == 200
        assert response.json()["machine_id"] == machine["id"]
    listing = (await client.get(path, headers=ADMIN)).json()
    assert len(listing) == 2
    assert all("key" not in entry and "secret_hash" not in entry for entry in listing)
    async with session_maker() as session:
        saved = list(await session.scalars(select(MachineKey)))
        assert all(len(k.secret_hash) == 64 and k.secret_hash not in (first["key"], second["key"]) for k in saved)
    for _ in range(2):
        assert (await client.delete(f"{path}/{first['id']}", headers=ADMIN)).status_code == 200
    assert (await client.get("/run", headers={"X-API-Key": first["key"]})).status_code == 401
    assert (await client.get("/run", headers={"X-API-Key": second["key"]})).status_code == 200
    assert (
        await client.patch(f"/api/v1/machines/{machine['id']}", headers=ADMIN, json={"is_active": False})
    ).status_code == 200
    assert (await client.get("/run", headers={"X-API-Key": second["key"]})).status_code == 401


async def test_root_is_optional_and_never_a_machine(http):
    client, app = http
    _machine, issued = await provision(client)
    assert (await client.get("/api/v1/machines")).status_code == 401
    assert (await client.get("/api/v1/machines", headers={"X-Root-API-Key": issued["key"]})).status_code == 401
    assert (await client.get("/run", headers=ADMIN)).status_code == 401
    assert (await client.get("/run", headers={"X-API-Key": ROOT})).status_code == 401
    assert (await client.get("/run", headers={"X-API-Key": issued["key"] + "x"})).status_code == 401
    app.dependency_overrides[get_api_key_settings] = lambda: ApiKeySettings(root_key=None)
    assert (await client.get("/api/v1/machines", headers=ADMIN)).status_code == 401
    assert (await client.get("/run", headers={"X-API-Key": issued["key"]})).status_code == 200


async def test_scope_allowlist_duplicate_name_and_expiry(http, session_maker):
    client, _ = http
    assert (
        await client.post("/api/v1/machines", headers=ADMIN, json={"name": "bad", "scopes": ["root"]})
    ).status_code == 400
    machine, issued = await provision(client)
    assert (await client.post("/api/v1/machines", headers=ADMIN, json={"name": "scheduler"})).status_code == 409
    path = f"/api/v1/machines/{machine['id']}"
    assert (await client.patch(path, headers=ADMIN, json={"scopes": ["root"]})).status_code == 400
    expired = get_current_utc_time() - timedelta(seconds=1)
    assert (
        await client.post(path + "/keys", headers=ADMIN, json={"label": "expired", "expires_at": expired.isoformat()})
    ).status_code == 400
    assert (
        await client.post(path + "/keys", headers=ADMIN, json={"label": "naive", "expires_at": "2030-01-01T00:00:00"})
    ).status_code == 422
    async with session_maker() as session:
        key = await session.scalar(select(MachineKey))
        key.expires_at = expired
        await session.commit()
    assert (await client.get("/run", headers={"X-API-Key": issued["key"]})).status_code == 401
    assert (await client.get(path + "/keys", headers=ADMIN)).status_code == 200


def test_weak_root_configuration_is_rejected():
    with pytest.raises(ValueError, match="32 characters"):
        ApiKeySettings(root_key="short")
    assert ApiKeySettings(root_key="").root_key is None


@pytest.mark.parametrize("offset", [9, -5])
async def test_expiry_keeps_the_same_instant_after_database_roundtrip(http, monkeypatch, offset):
    from app_prebuilt_auth.api_key import services

    client, _ = http
    now = datetime(2030, 1, 1, 12, tzinfo=UTC)
    monkeypatch.setattr(services, "get_current_utc_time", lambda: now)
    machine, _ = await provision(client)
    path = f"/api/v1/machines/{machine['id']}/keys"
    expiry = now + timedelta(hours=1)
    response = await client.post(
        path,
        headers=ADMIN,
        json={"label": "offset", "expires_at": expiry.astimezone(timezone(timedelta(hours=offset))).isoformat()},
    )
    assert response.status_code == 201
    issued = response.json()
    headers = {"X-API-Key": issued["key"]}
    assert (await client.get("/run", headers=headers)).status_code == 200
    monkeypatch.setattr(services, "get_current_utc_time", lambda: expiry)
    assert (await client.get("/run", headers=headers)).status_code == 401


async def test_key_metadata_always_has_explicit_utc_timestamps(http):
    client, _ = http
    machine, first = await provision(client)
    path = f"/api/v1/machines/{machine['id']}/keys"
    expiry = get_current_utc_time() + timedelta(hours=1)
    issued = (
        await client.post(path, headers=ADMIN, json={"label": "expiring", "expires_at": expiry.isoformat()})
    ).json()
    revoked = (await client.delete(f"{path}/{first['id']}", headers=ADMIN)).json()
    listing = (await client.get(path, headers=ADMIN)).json()
    for key in [first, issued, revoked, *listing]:
        for field in ("created_at", "expires_at", "revoked_at"):
            if key[field]:
                assert datetime.fromisoformat(key[field]).utcoffset() == timedelta(0)


def test_invalid_root_configuration_does_not_print_the_secret():
    secret = "invalid-but-still-sensitive"
    with pytest.raises(ValueError) as error:
        ApiKeySettings(root_key=secret)
    assert secret not in str(error.value)
