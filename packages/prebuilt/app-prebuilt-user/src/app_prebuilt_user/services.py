import functools
import hashlib
from datetime import timedelta
from typing import Annotated
from uuid import UUID, uuid4

import jwt
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
)
from app_layer_base.utils.time_util import get_current_utc_time
from fastapi import Depends
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app_prebuilt_user.config import AuthSettings, get_auth_settings

from .exceptions import PermissionDeniedException, UserAlreadyExistsException
from .models import User
from .passwords import PasswordHasher
from .repos import UserRepository
from .schemas import UserCreate, UserDbCreate, UserDbUpdate, UserUpdate


@functools.lru_cache
def _password_hasher() -> PasswordHasher:
    # One per process: building it hashes a dummy password, which is deliberately slow.
    return PasswordHasher()


class UserService(
    BaseGetServiceMixin[UserRepository, User, BaseContextKwargs],
    BaseGetMultiServiceMixin[UserRepository, User, BaseContextKwargs],
    BaseDeleteServiceMixin[UserRepository, User, BaseContextKwargs],
):
    """Service class for handling user-related operations."""

    def __init__(
        self,
        settings: Annotated[AuthSettings, Depends(get_auth_settings)],
        repo: Annotated[UserRepository, Depends()],
    ):
        self.settings: AuthSettings = settings
        self._repo = repo

        self.passwords = _password_hasher()

    @property
    def repo(self) -> UserRepository:
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs

    @property
    def jwt_algorithm(self) -> str:
        return self.settings.JWT_ALGORITHM

    async def validate_email_exists(self, session: AsyncSession, email: str | EmailStr) -> None:
        """Validate if an email exists."""
        if await self.repo.exists(session, where=User.email == str(email)):
            raise UserAlreadyExistsException()

    async def create_user(self, session: AsyncSession, obj_data: UserCreate) -> User:
        """Create a new user."""
        await self.validate_email_exists(session, obj_data.email)
        user_data = UserDbCreate(
            **obj_data.model_dump(),
            hashed_password=self.get_password_hash(obj_data.password.get_secret_value()),
        )
        return await self.repo.create(session, user_data)

    async def create_admin(self, session: AsyncSession, obj_data: UserCreate) -> User:
        """Create a new admin user."""
        await self.validate_email_exists(session, obj_data.email)
        user_data = UserDbCreate(
            **obj_data.model_dump(),
            is_superadmin=True,
            hashed_password=self.get_password_hash(obj_data.password.get_secret_value()),
        )
        return await self.repo.create(session, user_data)

    async def update_user(self, session: AsyncSession, obj_data: UserUpdate, user_id: UUID) -> User | None:
        """Update an existing user.

        Only fields explicitly provided by the caller are applied (partial update);
        unset fields are left untouched rather than overwritten with ``None``.
        """
        existing = await self.repo.get_by_pk(session, user_id)
        if (
            existing is not None
            and existing.email == str(self.settings.FIRST_USER_EMAIL)
            and obj_data.email is not None
            and str(obj_data.email) != existing.email
        ):
            raise PermissionDeniedException(message="The bootstrap account email is managed by deployment settings")
        user_data = UserDbUpdate(**obj_data.model_dump(exclude={"password"}, exclude_unset=True))
        if obj_data.password:
            user_data.hashed_password = self.get_password_hash(obj_data.password.get_secret_value())
        return await self.repo.update_by_pk(session, pk=user_id, obj_in=user_data)

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        """Get a user by email."""
        return await self.repo.get_by_email(session, email=email)

    async def authenticate(self, session: AsyncSession, email: str, password: str) -> User | None:
        user = await self.repo.get_by_email(session, email=email)
        if user is None or user.hashed_password is None or not user.is_active or user.approval_status != "approved":
            self.passwords.dummy_verify()
            return None

        if not self.is_valid_password(password, user.hashed_password):
            return None
        if self.passwords.needs_rehash(user.hashed_password):
            # The only moment the plain password is known: move an older hash to the current scheme.
            user.hashed_password = self.get_password_hash(password)
            await session.flush()
        return user

    def create_access_token(self, user: User) -> str:
        return self._create_token(user, "access", timedelta(minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES))

    def create_refresh_token(self, user: User) -> str:
        return self._create_token(
            user,
            "refresh",
            timedelta(days=self.settings.REFRESH_TOKEN_EXPIRE_DAYS),
            pwd=self.password_fingerprint(user),
        )

    @staticmethod
    def password_fingerprint(user: User) -> str:
        """Changes with the stored hash, so a refresh token dies with the password it was issued under.

        It is a digest of a salted hash, not of the password, and reveals nothing about either.
        """
        return hashlib.sha256((user.hashed_password or "").encode()).hexdigest()[:16]

    async def refresh_user(self, session: AsyncSession, refresh_token: str) -> User | None:
        """The active user a valid refresh token belongs to, or None."""
        try:
            payload = jwt.decode(
                refresh_token,
                self.settings.SECRET_KEY.get_secret_value(),
                algorithms=[self.jwt_algorithm],
                issuer=self.settings.JWT_ISSUER,
                audience=self.settings.JWT_AUDIENCE,
                leeway=self.settings.JWT_LEEWAY_SECONDS,
                options={"require": ["exp", "iat", "nbf", "iss", "aud", "sub", "typ"]},
            )
            if payload.get("typ") != "refresh":
                return None
            user = await self.get(session, obj_pk=UUID(str(payload["sub"])))
        except (jwt.PyJWTError, ValueError):
            return None
        if (
            user is None
            or not user.is_active
            or user.approval_status != "approved"
            or payload.get("ver", 0) != user.auth_version
            or payload.get("pwd") != self.password_fingerprint(user)
        ):
            return None
        return user

    def _create_token(self, user: User, typ: str, lifetime: timedelta, **claims: str) -> str:
        if not user.is_active or user.approval_status != "approved":
            raise PermissionDeniedException()
        now = get_current_utc_time()
        expire = now + lifetime

        payload = {
            # Standard JWT claims
            "iss": self.settings.JWT_ISSUER,
            "aud": self.settings.JWT_AUDIENCE,
            "sub": str(user.id),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": expire,
            "jti": str(uuid4()),
            "ver": user.auth_version,
            "typ": typ,
            # Backward-compat for existing code paths
            "user_id": str(user.id),
            **claims,
        }

        return jwt.encode(
            payload,
            key=self.settings.SECRET_KEY.get_secret_value(),
            algorithm=self.jwt_algorithm,
        )

    def is_valid_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.passwords.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return self.passwords.hash(password)

    async def ensure_first_user(self, session: AsyncSession) -> User:
        """Create the configured first superuser when it is missing; call once at startup.

        With ``FIRST_USER_SYNC_PASSWORD`` the account's password also follows ``FIRST_USER_PASSWORD``, for
        deployments that manage it in a secret store: changing the secret and restarting changes the password,
        which also ends the sessions issued under the old one.
        """
        email = str(self.settings.FIRST_USER_EMAIL)
        password = self.settings.FIRST_USER_PASSWORD.get_secret_value()
        user = await self.repo.get_by_email(session, email=email)
        if user is None:
            # Built directly: the operator chose this password in the deployment's settings, so the sign-up
            # rules of `UserCreate` do not apply to it.
            user = User(
                firstname="Admin",
                email=email,
                hashed_password=self.get_password_hash(password),
                is_active=True,
                is_verified=True,
                is_superadmin=True,
            )
            session.add(user)
            await session.flush()
            return user
        if self.settings.FIRST_USER_SYNC_PASSWORD and not (
            user.hashed_password and self.is_valid_password(password, user.hashed_password)
        ):
            user.hashed_password = self.get_password_hash(password)
            await session.flush()
        return user
