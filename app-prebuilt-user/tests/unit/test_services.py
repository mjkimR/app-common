import uuid

import jwt
import pytest
from app_layer_base.testing import random_email
from app_prebuilt_user.config.auth import AuthSettings
from app_prebuilt_user.exceptions import UserAlreadyExistsException
from app_prebuilt_user.models import User
from app_prebuilt_user.repos import UserRepository
from app_prebuilt_user.schemas import UserCreate, UserUpdate
from app_prebuilt_user.services import UserService

SECRET = "test-secret-key-not-for-production"


@pytest.fixture
def service() -> UserService:
    settings = AuthSettings(
        FIRST_USER_EMAIL="admin@example.com",
        FIRST_USER_PASSWORD="changeme123",
        SECRET_KEY=SECRET,
    )
    return UserService(settings=settings, repo=UserRepository())


def _payload(**overrides) -> UserCreate:
    data = {
        "firstname": "First",
        "lastname": "Last",
        "email": random_email(),
        "password": "password123",
    }
    data.update(overrides)
    return UserCreate(**data)


class TestCreateUser:
    async def test_password_is_hashed(self, session, service):
        user = await service.create_user(session, _payload(password="password123"))

        assert user.hashed_password is not None
        assert user.hashed_password != "password123"
        assert service.is_valid_password("password123", user.hashed_password)

    async def test_duplicate_email_raises(self, session, service):
        email = random_email()
        await service.create_user(session, _payload(email=email))
        await session.commit()

        with pytest.raises(UserAlreadyExistsException):
            await service.create_user(session, _payload(email=email))

    async def test_create_admin_sets_superadmin(self, session, service):
        user = await service.create_admin(session, _payload())

        assert user.is_superadmin is True


class TestAuthenticate:
    async def test_success(self, session, service):
        created = await service.create_user(session, _payload(password="password123"))
        await session.commit()

        authenticated = await service.authenticate(session, created.email, "password123")

        assert authenticated is not None
        assert authenticated.id == created.id

    async def test_wrong_password_returns_none(self, session, service):
        created = await service.create_user(session, _payload(password="password123"))
        await session.commit()

        assert await service.authenticate(session, created.email, "wrongpassword") is None

    async def test_unknown_email_returns_none(self, session, service):
        assert await service.authenticate(session, "nobody@example.com", "password123") is None


class TestUpdateUser:
    async def test_applies_fields_and_rehashes_password(self, session, service):
        created = await service.create_user(session, _payload(password="password123"))
        await session.commit()

        updated = await service.update_user(
            session,
            UserUpdate(firstname="Renamed", password="newpassword456"),
            created.id,
        )

        assert updated is not None
        assert updated.firstname == "Renamed"
        assert service.is_valid_password("newpassword456", updated.hashed_password)
        assert not service.is_valid_password("password123", updated.hashed_password)


class TestAccessToken:
    def test_roundtrip_encodes_expected_claims(self, service):
        user = User(id=uuid.uuid4())
        token = service.create_access_token(user)

        decoded = jwt.decode(
            token,
            key=SECRET,
            algorithms=["HS256"],
            audience="app-base",
            issuer="app-base",
        )

        assert decoded["sub"] == str(user.id)
        assert decoded["typ"] == "access"
