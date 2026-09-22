"""Exercise real request boundaries, including password rehash persistence."""

import bcrypt
import pytest
from app_layer_base.base.exceptions.handler import set_exception_handler
from app_layer_base.core.database.deps import get_session
from app_prebuilt_auth.user.api import v1_users_router
from app_prebuilt_auth.user.config import get_auth_settings
from app_prebuilt_auth.user.config.auth import AuthSettings
from app_prebuilt_auth.user.deps import get_login_throttle
from app_prebuilt_auth.user.models import User
from app_prebuilt_auth.user.repos import UserRepository
from app_prebuilt_auth.user.services import UserService
from app_prebuilt_auth.user.throttle import FailedLoginThrottle
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.real_commit
LOGIN = "/api/v1/users/login/"
REFRESH = "/api/v1/users/login/refresh"
CREDENTIALS = {"username": "admin@example.com", "password": "test-password"}


@pytest.fixture
async def auth_http(session, session_maker):
    settings = AuthSettings(
        FIRST_USER_EMAIL=CREDENTIALS["username"],
        FIRST_USER_PASSWORD=CREDENTIALS["password"],
        SECRET_KEY="test-signing-key-not-for-production",
    )
    service = UserService(settings, UserRepository())
    user = await service.ensure_first_user(session)
    await session.commit()

    async def request_session():
        async with session_maker() as fresh_session:
            yield fresh_session

    app = FastAPI()
    app.include_router(v1_users_router, prefix="/api/v1")
    set_exception_handler(app)
    app.dependency_overrides[get_session] = request_session
    app.dependency_overrides[get_auth_settings] = lambda: settings
    throttle = FailedLoginThrottle(5, 60, 300)
    app.dependency_overrides[get_login_throttle] = lambda: throttle
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, user.id


async def test_rehashed_password_persists_and_refresh_works_in_next_request(auth_http, session_maker):
    client, user_id = auth_http
    async with session_maker() as seed:
        user = await seed.get(User, user_id)
        user.hashed_password = bcrypt.hashpw(b"test-password", bcrypt.gensalt(rounds=4)).decode()
        await seed.commit()

    signed_in = await client.post(LOGIN, data=CREDENTIALS)
    assert signed_in.status_code == 200
    async with session_maker() as verification:
        persisted = await verification.get(User, user_id)
        assert persisted.hashed_password.startswith("$argon2id$")
    renewed = await client.post(REFRESH, json={"refresh_token": signed_in.json()["refresh_token"]})
    assert renewed.status_code == 200


async def test_bootstrap_user_can_be_read_and_listed(auth_http):
    client, user_id = auth_http
    tokens = (await client.post(LOGIN, data=CREDENTIALS)).json()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    profile = await client.get(f"/api/v1/users/{user_id}", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["lastname"] is None
    users = await client.get("/api/v1/users/admin/", headers=headers)
    assert users.status_code == 200


async def test_deactivated_user_cannot_reuse_access_or_refresh_token(auth_http, session_maker):
    client, user_id = auth_http
    tokens = (await client.post(LOGIN, data=CREDENTIALS)).json()
    async with session_maker() as update:
        user = await update.get(User, user_id)
        user.is_active = False
        await update.commit()
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.get(f"/api/v1/users/{user_id}", headers=headers)).status_code == 401
    assert (await client.get("/api/v1/users/admin/", headers=headers)).status_code == 401
    assert (await client.post(REFRESH, json={"refresh_token": tokens["refresh_token"]})).status_code == 401


async def test_swagger_token_url_accepts_the_password_form(auth_http):
    client, _ = auth_http
    schema = (await client.get("/openapi.json")).json()
    token_url = schema["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"]["password"]["tokenUrl"]
    assert (await client.post(token_url, data=CREDENTIALS)).status_code == 200


async def test_host_transaction_factory_is_used_for_login_and_admin_reads(auth_http, session_maker, monkeypatch):
    from functools import partial

    from app_layer_base.core.database import engine
    from app_layer_base.core.database.transaction import AsyncTransaction
    from app_prebuilt_auth.user.database import get_user_transaction

    client, _user_id = auth_http
    app = client._transport.app
    app.dependency_overrides[get_user_transaction] = lambda: partial(AsyncTransaction, session_maker)

    def wrong_database():
        raise AssertionError("The host supplied its own transaction factory")

    monkeypatch.setattr(engine, "get_session_maker", wrong_database)
    signed_in = await client.post(LOGIN, data=CREDENTIALS)
    assert signed_in.status_code == 200
    headers = {"Authorization": f"Bearer {signed_in.json()['access_token']}"}
    assert (await client.get("/api/v1/users/admin/", headers=headers)).status_code == 200
