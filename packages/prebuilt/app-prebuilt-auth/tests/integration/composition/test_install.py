import json
import os
import subprocess
import sys

import pytest
from app_layer_base.base.exceptions.handler import set_exception_handler
from app_prebuilt_auth import install_auth
from app_prebuilt_auth.api_key.config import ApiKeySettings
from app_prebuilt_auth.google.config import GoogleAuthSettings
from app_prebuilt_auth.models import User
from app_prebuilt_auth.user.config import AuthSettings
from app_prebuilt_auth.user.repos import UserRepository
from app_prebuilt_auth.user.services import UserService
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect, select

pytestmark = pytest.mark.real_commit
TABLES = {
    "users",
    "user_external_identities",
    "user_access_events",
    "google_login_flows",
    "api_key_machines",
    "api_keys",
}


def test_import_registers_the_entire_schema_without_settings():
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"SECRET_KEY", "FIRST_USER_EMAIL", "FIRST_USER_PASSWORD"}
    }
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json; import app_prebuilt_auth; from app_layer_base.base.models.mixin import Base; print(json.dumps(sorted(Base.metadata.tables)))",
        ],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert set(json.loads(result.stdout)) == TABLES


async def test_default_composition_keeps_all_tables_and_existing_routes(session):
    settings = AuthSettings(
        FIRST_USER_EMAIL="admin@example.com",
        FIRST_USER_PASSWORD="password-for-test",
        SECRET_KEY="test-only-auth-signing-key-not-production",
        REGISTRATION_REQUIRE_APPROVAL=True,
    )
    await UserService(settings, UserRepository()).ensure_first_user(session)
    await session.commit()
    app = FastAPI()
    install_auth(
        app,
        user_settings=settings,
        google_settings=GoogleAuthSettings(enabled=False),
        api_key_settings=ApiKeySettings(root_key=None),
    )
    set_exception_handler(app)
    connection = await session.connection()
    tables = await connection.run_sync(lambda conn: inspect(conn).get_table_names())
    assert set(tables) >= TABLES
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
        signed_in = await client.post(
            "/api/v1/users/login/", data={"username": "admin@example.com", "password": "password-for-test"}
        )
        assert signed_in.status_code == 200
        headers = {"Authorization": "Bearer " + signed_in.json()["access_token"]}
        assert (await client.get("/api/v1/users/admin/", headers=headers)).status_code == 200
        assert (await client.get("/api/v1/auth/google/options")).json() == {"enabled": False}
        assert (await client.get("/api/v1/auth/google/start")).status_code == 404
        assert (await client.get("/api/v1/machines")).status_code == 401
        schema = (await client.get("/openapi.json")).json()
        assert {"/api/v1/users/login/", "/api/v1/auth/google/callback", "/api/v1/machines"} <= schema["paths"].keys()
    assert (await session.scalar(select(User).where(User.email == "admin@example.com"))).is_superadmin


async def test_settings_are_scoped_to_each_application():
    first, second = FastAPI(), FastAPI()
    install_auth(first, google_settings=GoogleAuthSettings(enabled=False))
    install_auth(
        second,
        google_settings=GoogleAuthSettings(
            enabled=True,
            client_id="test-client",
            client_secret="test-secret",
            redirect_uri="https://hub.example/api/v1/auth/google/callback",
            frontend_url="https://hub.example/",
        ),
    )
    for app, enabled in [(first, False), (second, True)]:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://localhost") as client:
            assert (await client.get("/api/v1/auth/google/options")).json() == {"enabled": enabled}
