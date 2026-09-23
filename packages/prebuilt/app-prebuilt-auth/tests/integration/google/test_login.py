from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import pytest
from app_layer_base.base.exceptions.handler import set_exception_handler
from app_layer_base.core.database.deps import get_session
from app_prebuilt_auth.google.api import BROWSER_COOKIE, router
from app_prebuilt_auth.google.config import GoogleAuthSettings, get_google_auth_settings
from app_prebuilt_auth.google.models import GoogleLoginFlow
from app_prebuilt_auth.google.provider import GoogleIdentity, GoogleProvider
from app_prebuilt_auth.user.api import v1_users_router
from app_prebuilt_auth.user.config import AuthSettings, get_auth_settings
from app_prebuilt_auth.user.identities import ExternalIdentity
from app_prebuilt_auth.user.models import User
from app_prebuilt_auth.user.repos import UserRepository
from app_prebuilt_auth.user.services import UserService
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

pytestmark = pytest.mark.real_commit
BASE = "/api/v1/auth/google"


@pytest.fixture(params=["query", "form_post"])
async def login_http(session, session_maker, request):
    mode = request.param
    origin = "https://localhost" if mode == "form_post" else "http://localhost"
    settings = AuthSettings(
        FIRST_USER_EMAIL="admin@example.com",
        FIRST_USER_PASSWORD="test-password",
        SECRET_KEY="test-signing-key-for-google-auth",
        REGISTRATION_REQUIRE_APPROVAL=True,
    )
    google = GoogleAuthSettings(
        enabled=True,
        client_id="client",
        client_secret="secret",
        response_mode=mode,
        cookie_secure=mode == "form_post",
        redirect_uri=origin + BASE + "/callback",
        frontend_url=origin + "/",
    )
    service = UserService(settings, UserRepository())
    admin = await service.ensure_first_user(session)
    await session.commit()
    provider = GoogleProvider(google)
    provider.exchange = AsyncMock(
        return_value=GoogleIdentity(subject="google-subject", email="new@example.com", name="New")
    )
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(v1_users_router, prefix="/api/v1")
    set_exception_handler(app)

    async def request_session():
        async with session_maker() as fresh:
            yield fresh

    app.dependency_overrides[get_session] = request_session
    app.dependency_overrides[get_auth_settings] = lambda: settings
    app.dependency_overrides[get_google_auth_settings] = lambda: google
    app.dependency_overrides[GoogleProvider] = lambda: provider
    async with AsyncClient(transport=ASGITransport(app=app), base_url=origin) as client:
        yield client, provider, service.create_access_token(admin)


async def start(client):
    response = await client.get(BASE + "/start")
    assert response.status_code == 303
    query = parse_qs(urlsplit(response.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    mode = "form_post" if client.base_url.scheme == "https" else "query"
    assert query["response_mode"] == [mode]
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert ("secure" in cookie) == (mode == "form_post")
    assert f"samesite={'none' if mode == 'form_post' else 'lax'}" in cookie
    return query["state"][0]


async def callback(client, params):
    if client.base_url.scheme == "https":
        return await client.post(BASE + "/callback", data=params)
    return await client.get(BASE + "/callback", params=params)


async def sign_in(client):
    state = await start(client)
    response = await callback(client, {"state": state, "code": "valid-code"})
    assert response.status_code == 303
    assert response.headers["location"] == str(client.base_url).rstrip("/") + "/?google=complete"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    cookies = response.headers.get_list("set-cookie")
    assert any("app_google_exchange=" in cookie and "SameSite=lax" in cookie for cookie in cookies)
    return await client.post(BASE + "/exchange", headers={"Origin": str(client.base_url).rstrip("/")})


async def test_pending_approval_then_login_and_revocation(login_http, session_maker):
    client, _provider, admin_token = login_http
    first = await sign_in(client)
    assert first.json()["status"] == "pending"
    assert first.json()["tokens"] is None
    async with session_maker() as db:
        user = await db.scalar(select(User).where(User.email == "new@example.com"))
        user_id = str(user.id)
        assert not user.is_superadmin
        assert user.hashed_password is None
    headers = {"Authorization": "Bearer " + admin_token}
    url = "/api/v1/users/admin/" + user_id + "/access"
    approved = await client.post(url, headers=headers, json={"action": "approve", "expected_version": 0})
    assert approved.status_code == 200
    tokens = (await sign_in(client)).json()["tokens"]
    user_headers = {"Authorization": "Bearer " + tokens["access_token"]}
    assert (await client.get("/api/v1/users/me", headers=user_headers)).status_code == 200
    assert (await client.get("/api/v1/users/admin/", headers=user_headers)).status_code == 403
    assert (
        await client.post(url, headers=headers, json={"action": "suspend", "expected_version": 1})
    ).status_code == 200
    assert (await sign_in(client)).json()["status"] == "suspended"
    assert (
        await client.post(url, headers=headers, json={"action": "activate", "expected_version": 2})
    ).status_code == 200
    assert (await client.get("/api/v1/users/me", headers=user_headers)).status_code == 401
    assert (
        await client.post("/api/v1/users/login/refresh", json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 401
    stale = await client.post(url, headers=headers, json={"action": "reject", "expected_version": 1})
    assert stale.status_code == 409
    events = await client.get("/api/v1/users/admin/" + user_id + "/access-events", headers=headers)
    assert [event["action"] for event in events.json()] == ["activate", "suspend", "approve"]
    async with session_maker() as db:
        assert await db.scalar(select(func.count()).select_from(ExternalIdentity)) == 1


async def test_state_is_bound_to_browser_and_consumed_once(login_http):
    client, provider, _ = login_http
    state = await start(client)
    browser = client.cookies.get(BROWSER_COOKIE)
    client.cookies.clear()
    wrong = await callback(client, {"state": state, "code": "valid"})
    assert "google=failed" in wrong.headers["location"]
    provider.exchange.assert_not_called()
    client.cookies.set(BROWSER_COOKIE, browser, domain="localhost.local", path=BASE)
    success = await callback(client, {"state": state, "code": "valid"})
    assert "google=complete" in success.headers["location"]
    client.cookies.set(BROWSER_COOKIE, browser, domain="localhost.local", path=BASE)
    replay = await callback(client, {"state": state, "code": "valid"})
    assert "google=failed" in replay.headers["location"]
    assert provider.exchange.await_count == 1
    assert (await client.post(BASE + "/exchange", headers={"Origin": "https://evil.example"})).status_code == 401
    assert (
        await client.post(BASE + "/exchange", headers={"Origin": str(client.base_url).rstrip("/")})
    ).status_code == 200
    assert (
        await client.post(BASE + "/exchange", headers={"Origin": str(client.base_url).rstrip("/")})
    ).status_code == 401


async def test_existing_email_never_links_to_admin(login_http, session_maker):
    client, provider, _ = login_http
    provider.exchange.return_value = GoogleIdentity(subject="unlinked", email="admin@example.com", name="Admin")
    state = await start(client)
    result = await callback(client, {"state": state, "code": "valid"})
    assert "google=existing_account" in result.headers["location"]
    async with session_maker() as db:
        assert await db.scalar(select(func.count()).select_from(ExternalIdentity)) == 0


async def test_expired_state_is_not_accepted(login_http, session_maker):
    from datetime import timedelta

    from app_layer_base.utils.time_util import get_current_utc_time
    from sqlalchemy import update

    client, provider, _ = login_http
    state = await start(client)
    async with session_maker() as db:
        await db.execute(update(GoogleLoginFlow).values(expires_at=get_current_utc_time() - timedelta(seconds=1)))
        await db.commit()
    result = await callback(client, {"state": state, "code": "valid"})
    assert "google=failed" in result.headers["location"]
    provider.exchange.assert_not_called()


async def test_bootstrap_cannot_be_disabled_demoted_or_deleted(login_http):
    client, _, token = login_http
    headers = {"Authorization": "Bearer " + token}
    me = (await client.get("/api/v1/users/me", headers=headers)).json()
    url = "/api/v1/users/admin/" + me["id"]
    for action in ("suspend", "demote", "reject"):
        assert (
            await client.post(url + "/access", headers=headers, json={"action": action, "expected_version": 0})
        ).status_code == 409
    assert (await client.delete(url, headers=headers)).status_code in {400, 403}


async def test_concurrent_callback_is_consumed_once(login_http, is_postgres):
    import asyncio

    from app_prebuilt_auth.google.repos import GoogleAuthRepository
    from app_prebuilt_auth.google.services import GoogleAuthService
    from app_prebuilt_auth.google.usecases import GoogleAuthUseCase
    from app_prebuilt_auth.user.database import get_user_transaction
    from app_prebuilt_auth.user.exceptions import InvalidCredentialsException

    if not is_postgres:
        pytest.skip("PostgreSQL row locking contract")
    client, provider, _ = login_http
    settings = client._transport.app.dependency_overrides[get_auth_settings]()
    service = GoogleAuthService(GoogleAuthRepository(), provider, UserService(settings, UserRepository()))
    case = GoogleAuthUseCase(service, get_user_transaction())
    state = await start(client)
    browser = client.cookies.get(BROWSER_COOKIE)
    results = await asyncio.gather(
        case.callback(state, browser, "code"), case.callback(state, browser, "code"), return_exceptions=True
    )
    assert sum(isinstance(result, str) for result in results) == 1
    assert sum(isinstance(result, InvalidCredentialsException) for result in results) == 1
    assert provider.exchange.await_count == 1


async def test_approval_policy_can_be_disabled_by_other_hosts(login_http):
    client, _, _ = login_http
    settings = client._transport.app.dependency_overrides[get_auth_settings]()
    settings.REGISTRATION_REQUIRE_APPROVAL = False
    result = (await sign_in(client)).json()
    assert result["status"] == "approved"
    assert result["tokens"]["access_token"]


async def test_rejected_registration_gets_no_tokens(login_http, session_maker):
    client, _, admin_token = login_http
    await sign_in(client)
    async with session_maker() as db:
        user = await db.scalar(select(User).where(User.email == "new@example.com"))
        user_id = str(user.id)
    result = await client.post(
        "/api/v1/users/admin/" + user_id + "/access",
        headers={"Authorization": "Bearer " + admin_token},
        json={"action": "reject", "expected_version": 0},
    )
    assert result.status_code == 200
    rejected = (await sign_in(client)).json()
    assert rejected["status"] == "rejected"
    assert rejected["tokens"] is None


async def test_callback_rejects_the_unconfigured_method_without_consuming_state(login_http):
    client, provider, _ = login_http
    state = await start(client)
    params = {"state": state, "code": "valid"}
    if client.base_url.scheme == "https":
        response = await client.get(BASE + "/callback", params=params)
        assert response.headers["allow"] == "POST"
    else:
        response = await client.post(BASE + "/callback", data=params)
        assert response.headers["allow"] == "GET"
    assert response.status_code == 405
    assert "set-cookie" not in response.headers
    provider.exchange.assert_not_called()
    assert "google=complete" in (await callback(client, params)).headers["location"]


@pytest.mark.parametrize("params", [{"code": ""}, {"state": ""}, {"error": "access_denied"}])
async def test_callback_handles_missing_code_state_and_provider_cancellation(login_http, params):
    client, provider, _ = login_http
    state = await start(client)
    values = {"state": state, "code": "valid"} | params
    response = await callback(client, values)
    assert response.status_code == 303
    assert response.headers["location"] == str(client.base_url).rstrip("/") + "/?google=failed"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert client.cookies.get(BROWSER_COOKIE) is None
    provider.exchange.assert_not_called()


async def test_callback_provider_failure_consumes_state(login_http):
    client, provider, _ = login_http
    state = await start(client)
    browser = client.cookies.get(BROWSER_COOKIE)
    provider.exchange.side_effect = ValueError("Provider response must not be exposed")
    response = await callback(client, {"state": state, "code": "valid"})
    assert response.headers["location"] == str(client.base_url).rstrip("/") + "/?google=failed"
    client.cookies.set(BROWSER_COOKIE, browser, domain="localhost.local", path=BASE)
    await callback(client, {"state": state, "code": "valid"})
    assert provider.exchange.await_count == 1


async def test_post_callback_does_not_accept_query_parameters(login_http):
    client, provider, _ = login_http
    state = await start(client)
    response = await client.post(BASE + "/callback", params={"state": state, "code": "valid"})
    if client.base_url.scheme == "https":
        assert response.headers["location"] == str(client.base_url).rstrip("/") + "/?google=failed"
    else:
        assert response.status_code == 405
    provider.exchange.assert_not_called()
