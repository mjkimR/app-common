from uuid import UUID

from app_layer_base.utils.time_util import get_current_utc_time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import User, UserAccessEvent


class AccessRepository:
    async def lock_admins(self, session: AsyncSession) -> list[User]:
        return list(
            await session.scalars(
                select(User)
                .where(User.is_superadmin.is_(True))
                .order_by(User.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    async def lock_user(self, session: AsyncSession, user_id: UUID) -> User | None:
        return await session.scalar(
            select(User).where(User.id == user_id).with_for_update().execution_options(populate_existing=True)
        )

    async def record(
        self, session: AsyncSession, user_id: UUID, actor_id: UUID, action: str, reason: str | None
    ) -> None:
        session.add(
            UserAccessEvent(
                user_id=user_id, actor_id=actor_id, action=action, reason=reason, created_at=get_current_utc_time()
            )
        )
        await session.flush()

    async def refresh(self, session: AsyncSession, user: User) -> None:
        await session.refresh(user)

    async def events(self, session: AsyncSession, user_id: UUID) -> list[UserAccessEvent]:
        return list(
            await session.scalars(
                select(UserAccessEvent)
                .where(UserAccessEvent.user_id == user_id)
                .order_by(UserAccessEvent.created_at.desc(), UserAccessEvent.id.desc())
                .limit(50)
            )
        )
