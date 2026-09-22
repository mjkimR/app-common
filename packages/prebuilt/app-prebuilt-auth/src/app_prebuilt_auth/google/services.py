import base64
import hashlib
import secrets
from datetime import timedelta
from typing import Annotated

from app_layer_base.utils.time_util import get_current_utc_time
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app_prebuilt_auth.user.exceptions import UserAlreadyExistsException
from app_prebuilt_auth.user.models import User
from app_prebuilt_auth.user.services import UserService

from .models import GoogleLoginFlow
from .provider import GoogleIdentity, GoogleProvider
from .repos import GoogleAuthRepository


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


class GoogleAuthService:
    def __init__(
        self,
        repo: Annotated[GoogleAuthRepository, Depends()],
        provider: Annotated[GoogleProvider, Depends()],
        users: Annotated[UserService, Depends()],
    ):
        self.repo = repo
        self.provider = provider
        self.users = users

    async def begin(self, session: AsyncSession) -> tuple[str, str]:
        state, browser, nonce, verifier = (secrets.token_urlsafe(32) for _ in range(4))
        now = get_current_utc_time()
        await self.repo.clean_expired(session, now)
        await self.repo.save_flow(
            session,
            GoogleLoginFlow(
                key=digest(state),
                browser_hash=digest(browser),
                nonce=nonce,
                verifier=verifier,
                expires_at=now + timedelta(minutes=10),
            ),
        )
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        return self.provider.authorization_url(state, nonce, challenge), browser

    async def register(self, session: AsyncSession, identity: GoogleIdentity) -> User:
        user = await self.repo.identity_user(session, identity.subject)
        if user is not None:
            return user
        if (
            str(identity.email).casefold() == str(self.users.settings.FIRST_USER_EMAIL).casefold()
            or await self.repo.email_user(session, str(identity.email)) is not None
        ):
            # A verified Google email alone must never grant an existing account's privileges.
            raise UserAlreadyExistsException(message="Email already belongs to an account; use its existing login")
        return await self.repo.register(
            session,
            User(
                firstname=identity.name,
                email=str(identity.email),
                is_verified=True,
                is_active=True,
                is_superadmin=False,
                approval_status="pending" if self.users.settings.REGISTRATION_REQUIRE_APPROVAL else "approved",
            ),
            identity.subject,
        )

    async def handoff(self, session: AsyncSession, user: User) -> str:
        exchange = secrets.token_urlsafe(32)
        await self.repo.save_flow(
            session,
            GoogleLoginFlow(
                key=digest(exchange),
                browser_hash=digest(exchange),
                user_id=user.id,
                expires_at=get_current_utc_time() + timedelta(minutes=1),
            ),
        )
        return exchange
