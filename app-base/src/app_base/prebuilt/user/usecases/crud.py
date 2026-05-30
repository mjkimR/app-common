from typing import Annotated
from uuid import UUID

from app_layer_base.base.services.base import BaseContextKwargs
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends

from ..exceptions import PermissionDeniedException
from ..models import User
from ..schemas import UserUpdate
from ..services import UserService


class GetUserUseCase(BaseUseCase):
    def __init__(self, service: Annotated[UserService, Depends()]):
        self.service = service

    async def execute(
        self,
        user_id: UUID,
        current_user: User,
        context: BaseContextKwargs | None = None,
    ) -> User | None:
        if current_user.id == user_id:
            return current_user
        if not current_user.is_superadmin:
            raise PermissionDeniedException()
        async with AsyncTransaction() as session:
            return await self.service.get(session, user_id, context=context)


class UpdateUserUseCase(BaseUseCase):
    def __init__(self, service: Annotated[UserService, Depends()]):
        self.service = service

    async def execute(
        self,
        obj_data: UserUpdate,
        user_id: UUID,
        current_user: User,
        context: BaseContextKwargs | None = None,
    ) -> User | None:
        if current_user.id == user_id:
            return current_user
        if not current_user.is_superadmin:
            raise PermissionDeniedException()
        async with AsyncTransaction() as session:
            return await self.service.update_user(session, obj_data, user_id)
