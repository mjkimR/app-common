from __future__ import annotations

from typing import Annotated
from uuid import UUID

from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from app_layer_base.base.services.base import BaseContextKwargs
from app_layer_base.base.usecases.crud import BaseGetMultiUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..access_repo import AccessRepository
from ..database import UserTransaction, get_user_transaction
from ..exceptions import PermissionDeniedException, UserCantDeleteItselfException
from ..models import User
from ..schemas import UserCreate
from ..services import UserService
from .base import UserUseCase


class GetMultiUserUseCase(BaseGetMultiUseCase[UserService, User, BaseContextKwargs]):
    def __init__(
        self,
        service: Annotated[UserService, Depends()],
        transaction: Annotated[UserTransaction, Depends(get_user_transaction)] = AsyncTransaction,
    ):
        super().__init__(service)
        self.transaction = transaction

    async def execute(
        self,
        query_options: ListQueryOptions | None = None,
        context: BaseContextKwargs | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> PaginatedList[User]:
        if session is not None:
            return await super().execute(query_options, context, session=session)
        async with self.transaction() as owned:
            return await super().execute(query_options, context, session=owned)


class DeleteUserUseCase(UserUseCase):
    async def execute(
        self,
        user_id: UUID,
        current_user: User,
        context: BaseContextKwargs | None = None,
    ) -> DeleteResponse:
        if current_user.id == user_id:
            raise UserCantDeleteItselfException()
        async with self.transaction() as session:
            repo = AccessRepository()
            admins = await repo.lock_admins(session)
            actor = next((user for user in admins if user.id == current_user.id), None)
            if actor is None or not actor.is_active or actor.approval_status != "approved":
                raise PermissionDeniedException()
            target = await repo.lock_user(session, user_id)
            # Administrator accounts are retained for recovery and audit. Demote first.
            if target is not None and (
                target.is_superadmin or target.email == str(self.service.settings.FIRST_USER_EMAIL)
            ):
                raise PermissionDeniedException(message="Administrator accounts must be retained")
            if target is not None:
                await repo.record(session, target.id, actor.id, "delete", None)
            return await self.service.delete(session, user_id, context=context)


class CreateUserUseCase(UserUseCase):
    async def execute(self, obj_data: UserCreate, context: BaseContextKwargs | None = None) -> User:
        async with self.transaction() as session:
            return await self.service.create_user(session, obj_data)


class CreateAdminUseCase(UserUseCase):
    async def execute(self, obj_data: UserCreate, context: BaseContextKwargs | None = None) -> User:
        async with self.transaction() as session:
            return await self.service.create_admin(session, obj_data)
