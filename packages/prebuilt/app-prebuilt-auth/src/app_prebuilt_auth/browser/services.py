import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from app_layer_base.utils.time_util import get_current_utc_time
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app_prebuilt_auth.user.exceptions import InvalidCredentialsException
from app_prebuilt_auth.user.services import UserService
from app_prebuilt_auth.user.token_schemas import Token

from .models import BrowserSession
from .repos import BrowserSessionRepository


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class BrowserSessionService:
    def __init__(
        self,
        users: Annotated[UserService, Depends()],
        repo: Annotated[BrowserSessionRepository, Depends()],
    ):
        self.users, self.repo = users, repo

    @property
    def lifetime(self) -> timedelta:
        return timedelta(days=self.users.settings.REFRESH_TOKEN_EXPIRE_DAYS)

    async def begin(self, session: AsyncSession, refresh_token: str, previous: str) -> str:
        user = await self.users.refresh_user(session, refresh_token)
        if user is None:
            raise InvalidCredentialsException()
        now = get_current_utc_time()
        key = secrets.token_urlsafe(32)
        await self.repo.prune(session, now)
        await self.repo.revoke(session, digest(previous))
        await self.repo.create(
            session,
            BrowserSession(
                key_hash=digest(key),
                user_id=user.id,
                auth_version=user.auth_version,
                password_fingerprint=self.users.password_fingerprint(user),
                expires_at=now + self.lifetime,
            ),
        )
        return key

    async def refresh(self, session: AsyncSession, key: str) -> Token:
        now = get_current_utc_time()
        record = await self.repo.renew(session, digest(key), now, now + self.lifetime)
        user = await self.users.get(session, obj_pk=record.user_id) if record else None
        if (
            record is None
            or user is None
            or not user.is_active
            or user.approval_status != "approved"
            or record.auth_version != user.auth_version
            or record.password_fingerprint != self.users.password_fingerprint(user)
        ):
            raise InvalidCredentialsException()
        return Token(
            access_token=self.users.create_access_token(user),
            token_type="bearer",
            expires_in=self.users.settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
