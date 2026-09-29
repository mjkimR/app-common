from datetime import datetime

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import BrowserSession


class BrowserSessionRepository:
    async def create(self, session: AsyncSession, value: BrowserSession) -> None:
        session.add(value)
        await session.flush()

    async def renew(
        self, session: AsyncSession, key_hash: str, now: datetime, expires_at: datetime
    ) -> BrowserSession | None:
        # An atomic write serializes refresh/logout on PostgreSQL and SQLite. A revoked
        # session is never inserted again by an in-flight renewal.
        return await session.scalar(
            update(BrowserSession)
            .where(BrowserSession.key_hash == key_hash, BrowserSession.expires_at > now)
            .values(expires_at=expires_at)
            .returning(BrowserSession)
        )

    async def revoke(self, session: AsyncSession, key_hash: str) -> None:
        await session.execute(delete(BrowserSession).where(BrowserSession.key_hash == key_hash))

    async def prune(self, session: AsyncSession, now: datetime) -> None:
        await session.execute(delete(BrowserSession).where(BrowserSession.expires_at <= now))
