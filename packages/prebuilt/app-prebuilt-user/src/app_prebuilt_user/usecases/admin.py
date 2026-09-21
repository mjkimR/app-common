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

from ..database import UserTransaction, get_user_transaction
from ..exceptions import UserCantDeleteItselfException
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
            return await self.service.delete(session, user_id, context=context)


class CreateUserUseCase(UserUseCase):
    async def execute(self, obj_data: UserCreate, context: BaseContextKwargs | None = None) -> User:
        async with self.transaction() as session:
            return await self.service.create_user(session, obj_data)


class CreateAdminUseCase(UserUseCase):
    async def execute(self, obj_data: UserCreate, context: BaseContextKwargs | None = None) -> User:
        async with self.transaction() as session:
            return await self.service.create_admin(session, obj_data)
