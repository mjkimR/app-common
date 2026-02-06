from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends

from ..exceptions import UserCantDeleteItselfException
from ..models import User
from ..schemas import UserCreate
from ..services import UserService
from app_base.base.schemas.delete_resp import DeleteResponse
from app_base.base.services.base import BaseContextKwargs, TContextKwargs
from app_base.base.usecases.base import BaseUseCase
from app_base.base.usecases.crud import BaseGetMultiUseCase
from app_base.core.database.transaction import AsyncTransaction


class GetMultiUserUseCase(BaseGetMultiUseCase[UserService, User, BaseContextKwargs]):
    def __init__(self, service: Annotated[UserService, Depends()]):
        super().__init__(service)


class DeleteUserUseCase(BaseUseCase):
    def __init__(self, service: Annotated[UserService, Depends()]):
        self.service = service

    async def execute(
        self,
        user_id: UUID,
        current_user: User,
        context: Optional[TContextKwargs] = None,
    ) -> DeleteResponse:
        if current_user.id == user_id:
            raise UserCantDeleteItselfException()
        async with AsyncTransaction() as session:
            return await self.service.delete(session, user_id, context=context)


class CreateUserUseCase(BaseUseCase):
    def __init__(self, service: Annotated[UserService, Depends()]):
        self.service = service

    async def execute(self, obj_data: UserCreate, context: Optional[TContextKwargs] = None) -> User:
        async with AsyncTransaction() as session:
            return await self.service.create_user(session, obj_data)


class CreateAdminUseCase(BaseUseCase):
    def __init__(self, service: Annotated[UserService, Depends()]):
        self.service = service

    async def execute(self, obj_data: UserCreate, context: Optional[TContextKwargs] = None) -> User:
        async with AsyncTransaction() as session:
            return await self.service.create_admin(session, obj_data)
