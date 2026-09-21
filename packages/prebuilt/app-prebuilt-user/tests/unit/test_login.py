import bcrypt
import jwt
import pytest
from app_layer_base.testing import random_email
from app_prebuilt_user.api.v1.login import login, refresh
from app_prebuilt_user.config.auth import AuthSettings
from app_prebuilt_user.exceptions import (
    IncorrectEmailOrPasswordException,
    InvalidCredentialsException,
    TooManyLoginAttemptsException,
)
from app_prebuilt_user.repos import UserRepository
from app_prebuilt_user.schemas import UserCreate, UserUpdate
from app_prebuilt_user.services import UserService
from app_prebuilt_user.throttle import FailedLoginThrottle
from app_prebuilt_user.token_schemas import RefreshRequest

SECRET = "test-secret-key-not-for-production"


def make_service(**settings) -> UserService:
    values = {"FIRST_USER_EMAIL": "admin@example.com", "FIRST_USER_PASSWORD": "short", "SECRET_KEY": SECRET}
    return UserService(settings=AuthSettings(**{**values, **settings}), repo=UserRepository())


@pytest.fixture
def service() -> UserService:
    return make_service()


async def make_user(session, service: UserService, password: str = "password123"):
    user = await service.create_user(
        session, UserCreate(firstname="First", lastname="Last", email=random_email(), password=password)
    )
    await session.commit()
    return user


class Form:
    def __init__(self, username: str, password: str) -> None:
        self.username, self.password = username, password


async def sign_in(session, service, email, password, throttle=None, caller="203.0.113.7", locked=None):
    async def on_lockout(address: str) -> None:
        if locked is not None:
            locked.append(address)

    return await login(
        Form(email, password),  # type: ignore[arg-type]
        session,
        service,
        throttle or FailedLoginThrottle(5, 60, 300),
        caller,
        on_lockout,
    )


def claims(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"], audience="app-base", issuer="app-base")


class TestLogin:
    async def test_a_login_returns_an_access_and_a_refresh_token(self, session, service):
        user = await make_user(session, service)

        token = await sign_in(session, service, user.email, "password123")

        assert token.token_type == "bearer" and token.expires_in == 600
        assert (claims(token.access_token)["typ"], claims(token.access_token)["sub"]) == ("access", str(user.id))
        assert token.refresh_token is not None and claims(token.refresh_token)["typ"] == "refresh"

    async def test_a_bcrypt_hash_is_moved_to_argon2_by_the_first_login(self, session, service):
        user = await make_user(session, service)
        user.hashed_password = bcrypt.hashpw(b"password123", bcrypt.gensalt(rounds=4)).decode()
        await session.commit()

        await sign_in(session, service, user.email, "password123")

        await session.refresh(user)
        assert user.hashed_password.startswith("$argon2id$")
        assert service.is_valid_password("password123", user.hashed_password)

    async def test_an_inactive_user_cannot_log_in(self, session, service):
        user = await make_user(session, service)
        user.is_active = False
        await session.commit()

        with pytest.raises(IncorrectEmailOrPasswordException):
            await sign_in(session, service, user.email, "password123")

    async def test_repeated_failures_lock_the_caller_out_even_with_the_right_password(self, session, service):
        user = await make_user(session, service)
        throttle = FailedLoginThrottle(max_failures=3, window_seconds=60, lockout_seconds=300)
        locked: list[str] = []

        for _ in range(3):
            with pytest.raises(IncorrectEmailOrPasswordException):
                await sign_in(session, service, user.email, "wrong-password", throttle, locked=locked)
        with pytest.raises(TooManyLoginAttemptsException) as refused:
            await sign_in(session, service, user.email, "password123", throttle, locked=locked)

        assert refused.value.status_code == 429 and int(refused.value.retry_after or 0) > 0
        # Told once, when the lockout starts; another caller is unaffected.
        assert locked == ["203.0.113.7"]
        assert await sign_in(session, service, user.email, "password123", throttle, caller="198.51.100.9")


class TestRefresh:
    async def test_a_refresh_token_is_exchanged_for_a_new_pair(self, session, service):
        user = await make_user(session, service)
        first = await sign_in(session, service, user.email, "password123")

        renewed = await refresh(RefreshRequest(refresh_token=first.refresh_token or ""), session, service)

        assert claims(renewed.access_token)["sub"] == str(user.id)
        assert renewed.refresh_token and renewed.refresh_token != first.refresh_token

    async def test_only_a_refresh_token_refreshes(self, session, service):
        user = await make_user(session, service)
        token = await sign_in(session, service, user.email, "password123")

        for value in (token.access_token, "not-a-token", ""):
            with pytest.raises(InvalidCredentialsException) as refused:
                await refresh(RefreshRequest(refresh_token=value), session, service)
            assert refused.value.status_code == 401

    async def test_a_refresh_token_dies_with_its_password_or_its_user(self, session, service):
        user = await make_user(session, service)
        token = await sign_in(session, service, user.email, "password123")

        await service.update_user(session, UserUpdate(password="another-password"), user.id)
        await session.commit()
        with pytest.raises(InvalidCredentialsException):
            await refresh(RefreshRequest(refresh_token=token.refresh_token or ""), session, service)

        again = await sign_in(session, service, user.email, "another-password")
        user.is_active = False
        await session.commit()
        with pytest.raises(InvalidCredentialsException):
            await refresh(RefreshRequest(refresh_token=again.refresh_token or ""), session, service)


class TestFirstUser:
    async def test_the_first_superuser_is_created_once_with_the_configured_password(self, session, service):
        created = await service.ensure_first_user(session)
        again = await service.ensure_first_user(session)

        assert created.id == again.id
        assert (created.email, created.is_superadmin, created.is_active) == ("admin@example.com", True, True)
        # The operator's password is not subject to the sign-up rules (it is shorter than eight characters here).
        assert await service.authenticate(session, "admin@example.com", "short") is not None

    async def test_a_changed_password_is_left_alone_unless_the_settings_are_the_source_of_truth(self, session):
        await make_service().ensure_first_user(session)

        await make_service(FIRST_USER_PASSWORD="rotated").ensure_first_user(session)
        assert await make_service().authenticate(session, "admin@example.com", "short") is not None

        syncing = make_service(FIRST_USER_PASSWORD="rotated", FIRST_USER_SYNC_PASSWORD=True)
        user = await syncing.ensure_first_user(session)
        hashed = user.hashed_password
        assert await syncing.authenticate(session, "admin@example.com", "rotated") is not None
        assert await syncing.authenticate(session, "admin@example.com", "short") is None
        # An unchanged password is not hashed again, so sessions survive a restart.
        assert (await syncing.ensure_first_user(session)).hashed_password == hashed
