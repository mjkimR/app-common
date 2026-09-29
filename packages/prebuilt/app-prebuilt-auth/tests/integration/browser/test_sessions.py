from datetime import timedelta
from functools import partial

import pytest
from app_layer_base.base.exceptions.handler import set_exception_handler
from app_layer_base.core.database.transaction import AsyncTransaction
from app_layer_base.utils.time_util import get_current_utc_time
from app_prebuilt_auth.browser.api import router
from app_prebuilt_auth.browser.config import BrowserAuthSettings, get_browser_auth_settings
from app_prebuilt_auth.browser.models import BrowserSession
from app_prebuilt_auth.browser.services import digest
from app_prebuilt_auth.user.config import AuthSettings, get_auth_settings
from app_prebuilt_auth.user.database import get_user_transaction
from app_prebuilt_auth.user.deps import get_login_throttle
from app_prebuilt_auth.user.models import User
from app_prebuilt_auth.user.repos import UserRepository
from app_prebuilt_auth.user.services import UserService
from app_prebuilt_auth.user.throttle import FailedLoginThrottle
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

pytestmark = pytest.mark.real_commit
BASE = "/api/v1/auth/browser"
ORIGIN = "https://app.example.com"
HEADERS = {"Origin": ORIGIN, "X-Browser-Session": "1"}
CREDENTIALS = {"username": "browser@example.com", "password": "browser-test-password"}


@pytest.fixture
async def browser(session, session_maker):
    settings = AuthSettings(
        FIRST_USER_EMAIL=CREDENTIALS["username"],
        FIRST_USER_PASSWORD=CREDENTIALS["password"],
        SECRET_KEY="browser-test-signing-key-at-least-32-characters",
    )
    service = UserService(settings, UserRepository())
    await service.ensure_first_user(session)
    await session.commit()
    get_login_throttle.cache_clear()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    set_exception_handler(app)
    app.dependency_overrides[get_auth_settings] = lambda: settings
    throttle = FailedLoginThrottle(5, 60, 300)
    app.dependency_overrides[get_login_throttle] = lambda: throttle
    app.dependency_overrides[get_user_transaction] = lambda: partial(AsyncTransaction, session_maker)
    app.dependency_overrides[get_browser_auth_settings] = lambda: BrowserAuthSettings()
    async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN, headers=HEADERS) as client:
        yield client, service
    get_login_throttle.cache_clear()


async def sign_in(client):
    response = await client.post(BASE + "/login", data=CREDENTIALS)
    assert response.status_code == 200, response.text
    return response


async def test_persistent_http_only_cookie_restores_without_a_body(browser, session_maker):
    client, _ = browser
    response = await sign_in(client)
    assert "refresh_token" not in response.json()
    assert response.headers["cache-control"] == "no-store"
    cookie = response.headers["set-cookie"]
    assert all(
        value in cookie for value in ["HttpOnly", "Secure", "SameSite=lax", "Max-Age=1209600", "Path=/api/v1/auth"]
    )
    key = client.cookies.get("app_refresh")
    async with session_maker() as db:
        record = await db.scalar(select(BrowserSession))
        assert record.key_hash == digest(key) and record.key_hash != key
    for _ in range(2):
        # A fresh page has no bearer or JS refresh token; its cookie is sufficient.
        renewed = await client.post(BASE + "/refresh")
        assert renewed.status_code == 200
        assert renewed.json()["access_token"] and "refresh_token" not in renewed.json()
        assert client.cookies.get("app_refresh") == key


async def test_logout_revokes_copied_cookie_and_is_idempotent(browser):
    client, _ = browser
    await sign_in(client)
    key = client.cookies.get("app_refresh")
    assert (await client.post(BASE + "/logout")).status_code == 204
    assert client.cookies.get("app_refresh") is None
    assert (await client.post(BASE + "/logout")).status_code == 204
    client.cookies.set("app_refresh", key, path="/api/v1/auth")
    assert (await client.post(BASE + "/refresh")).status_code == 401


@pytest.mark.parametrize("change", ["password", "inactive", "approval", "version", "expiry"])
async def test_session_cannot_outlive_account_or_expiry(browser, session_maker, change):
    client, service = browser
    await sign_in(client)
    async with session_maker() as db:
        if change == "expiry":
            await db.execute(update(BrowserSession).values(expires_at=get_current_utc_time() - timedelta(seconds=1)))
        else:
            values = {
                "password": {"hashed_password": service.get_password_hash("changed-password")},
                "inactive": {"is_active": False},
                "approval": {"approval_status": "suspended"},
                "version": {"auth_version": 1},
            }[change]
            await db.execute(update(User).values(**values))
        await db.commit()
    assert (await client.post(BASE + "/refresh")).status_code == 401


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Origin": ORIGIN},
        {"X-Browser-Session": "1"},
        {"Origin": "https://evil.example.com", "X-Browser-Session": "1"},
        {"Origin": "null", "X-Browser-Session": "1"},
    ],
)
async def test_csrf_is_rejected_for_every_cookie_mutation(browser, headers):
    client, _ = browser
    await sign_in(client)
    client.headers.clear()
    for path in ["login", "refresh", "logout"]:
        response = await client.post(BASE + "/" + path, headers=headers, data=CREDENTIALS if path == "login" else None)
        assert response.status_code == 403
    assert (await client.post(BASE + "/refresh", headers=HEADERS)).status_code == 200


async def test_relogin_replaces_only_this_browser_session(browser):
    client, _ = browser
    await sign_in(client)
    old = client.cookies.get("app_refresh")
    await sign_in(client)
    assert client.cookies.get("app_refresh") != old
    client.cookies.clear()
    client.cookies.set("app_refresh", old, path="/api/v1/auth")
    assert (await client.post(BASE + "/refresh")).status_code == 401


async def test_password_lockout_also_applies_to_browser_login(browser):
    client, _ = browser
    for _ in range(5):
        response = await client.post(BASE + "/login", data={**CREDENTIALS, "password": "wrong"})
        assert response.status_code == 400
    response = await client.post(BASE + "/login", data=CREDENTIALS)
    assert response.status_code == 429


async def test_concurrent_refresh_and_logout_cannot_resurrect_session(browser, is_postgres):
    if not is_postgres:
        pytest.skip("Concurrent transactions require the PostgreSQL test leg")
    import asyncio

    client, _ = browser
    await sign_in(client)
    cookie = {"Cookie": "app_refresh=" + client.cookies.get("app_refresh")}
    results = await asyncio.gather(
        client.post(BASE + "/refresh", headers=cookie),
        client.post(BASE + "/refresh", headers=cookie),
        client.post(BASE + "/logout", headers=cookie),
    )
    assert results[2].status_code == 204
    assert all(result.status_code in {200, 401} for result in results[:2])
    assert (await client.post(BASE + "/refresh", headers=cookie)).status_code == 401
