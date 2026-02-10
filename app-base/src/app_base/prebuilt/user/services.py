from datetime import datetime, timedelta, timezone
from typing import Annotated, Union
from uuid import UUID, uuid4

import jwt
from app_base.base.services.base import (
    BaseContextKwargs,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
)
from app_base.config import AuthSettings, get_auth_settings
from fastapi import Depends
from passlib.context import CryptContext
from pydantic import EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from .exceptions import UserAlreadyExistsException
from .models import User
from .repos import UserRepository
from .schemas import UserCreate, UserDbCreate, UserDbUpdate, UserUpdate


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

        self.context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    @property
    def repo(self) -> UserRepository:
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs

    @property
    def jwt_algorithm(self) -> str:
        return self.settings.JWT_ALGORITHM

    async def validate_email_exists(self, session: AsyncSession, email: Union[str, EmailStr]) -> None:
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
        """Update an existing user."""
        user_data = UserDbUpdate(**obj_data.model_dump(exclude={"password"}))
        if obj_data.password:
            user_data.hashed_password = self.get_password_hash(obj_data.password.get_secret_value())
        return await self.repo.update_by_pk(session, pk=user_id, obj_in=user_data)

    async def get_by_email(self, session: AsyncSession, email: str) -> User | None:
        """Get a user by email."""
        return await self.repo.get_by_email(session, email=email)

    async def authenticate(self, session: AsyncSession, email: str, password: str) -> User | None:
        user = await self.repo.get_by_email(session, email=email)
        if user is not None and self.is_valid_password(password, user.hashed_password):
            return user
        return None

    def create_access_token(self, user: User) -> str:
        now = datetime.now(tz=timezone.utc)
        expire = now + timedelta(minutes=self.settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        payload = {
            # Standard JWT claims
            "iss": self.settings.JWT_ISSUER,
            "aud": self.settings.JWT_AUDIENCE,
            "sub": str(user.id),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "exp": expire,
            "jti": str(uuid4()),
            # Token type (useful when adding refresh token later)
            "typ": "access",
            # Backward-compat for existing code paths
            "user_id": str(user.id),
        }

        return jwt.encode(
            payload,
            key=self.settings.SECRET_KEY.get_secret_value(),
            algorithm=self.jwt_algorithm,
        )

    def is_valid_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return self.context.hash(password)
