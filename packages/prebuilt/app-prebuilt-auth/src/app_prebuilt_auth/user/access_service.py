from typing import Annotated
from uuid import UUID

from app_layer_base.base.exceptions.basic import ConflictException
from app_layer_base.utils.time_util import get_current_utc_time
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from .access_repo import AccessRepository
from .config import AuthSettings, get_auth_settings
from .exceptions import PermissionDeniedException, UserNotFoundException
from .models import User
from .schemas import UserAccessChange


class AccessService:
    def __init__(
        self,
        repo: Annotated[AccessRepository, Depends()],
        settings: Annotated[AuthSettings, Depends(get_auth_settings)],
    ):
        self.repo = repo
        self.settings = settings

    async def change(self, session: AsyncSession, user_id: UUID, data: UserAccessChange, actor_id: UUID) -> User:
        # Serialize administrator changes before locking individual accounts.
        admins = await self.repo.lock_admins(session)
        actor = next((user for user in admins if user.id == actor_id), None)
        if actor is None or not actor.is_active or actor.approval_status != "approved":
            raise PermissionDeniedException()
        user = await self.repo.lock_user(session, user_id)
        if user is None:
            raise UserNotFoundException()
        if user.auth_version != data.expected_version:
            raise ConflictException(message="Account changed; reload before saving")
        reducing = data.action in {"reject", "suspend", "demote"}
        if reducing and (user.id == actor_id or user.email == str(self.settings.FIRST_USER_EMAIL)):
            raise ConflictException(message="The current administrator and bootstrap account must retain access")
        if (
            reducing
            and user.is_superadmin
            and sum(u.is_active and u.approval_status == "approved" for u in admins) <= 1
        ):
            raise ConflictException(message="Keep at least one active approved administrator")
        if data.action in {"promote", "activate"} and user.approval_status != "approved":
            raise ConflictException(message="Approve the account first")
        if data.action == "approve":
            user.approval_status = "approved"
        elif data.action == "reject":
            user.approval_status = "rejected"
        elif data.action in {"suspend", "activate"}:
            user.is_active = data.action == "activate"
        else:
            user.is_superadmin = data.action == "promote"
        # Re-enabling an account must not resurrect old sessions.
        user.auth_version += 1
        user.updated_at = get_current_utc_time()
        await self.repo.record(session, user.id, actor_id, data.action, data.reason)
        await self.repo.refresh(session, user)
        return user
