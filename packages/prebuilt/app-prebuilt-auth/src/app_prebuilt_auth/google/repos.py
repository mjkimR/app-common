from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app_prebuilt_auth.user.identities import ExternalIdentity
from app_prebuilt_auth.user.models import User

from .models import GoogleLoginFlow


class GoogleAuthRepository:
    async def consume(
        self, session: AsyncSession, key: str, browser_hash: str, now: datetime
    ) -> GoogleLoginFlow | None:
        # DELETE RETURNING is atomic across Cloud Run workers and prevents callback replay.
        return await session.scalar(
            delete(GoogleLoginFlow)
            .where(
                GoogleLoginFlow.key == key,
                GoogleLoginFlow.browser_hash == browser_hash,
                GoogleLoginFlow.expires_at > now,
            )
            .returning(GoogleLoginFlow)
        )

    async def save_flow(self, session: AsyncSession, flow: GoogleLoginFlow) -> None:
        session.add(flow)
        await session.flush()

    async def clean_expired(self, session: AsyncSession, now: datetime) -> None:
        await session.execute(delete(GoogleLoginFlow).where(GoogleLoginFlow.expires_at <= now))

    async def identity_user(self, session: AsyncSession, subject: str) -> User | None:
        return await session.scalar(
            select(User)
            .join(ExternalIdentity, ExternalIdentity.user_id == User.id)
            .where(ExternalIdentity.issuer == "https://accounts.google.com", ExternalIdentity.subject == subject)
        )

    async def user(self, session: AsyncSession, user_id: UUID) -> User | None:
        return await session.get(User, user_id)

    async def email_user(self, session: AsyncSession, email: str) -> User | None:
        return await session.scalar(select(User).where(func.lower(User.email) == email.lower()))

    async def register(self, session: AsyncSession, user: User, subject: str) -> User:
        session.add(user)
        await session.flush()
        session.add(ExternalIdentity(user_id=user.id, issuer="https://accounts.google.com", subject=subject))
        await session.flush()
        return user
