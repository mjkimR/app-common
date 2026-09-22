from uuid import UUID

from app_layer_base.base.services.base import BaseContextKwargs

from ..exceptions import PermissionDeniedException
from ..models import User
from ..schemas import UserUpdate
from .base import UserUseCase


class GetUserUseCase(UserUseCase):
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
        async with self.transaction() as session:
            return await self.service.get(session, user_id, context=context)


class UpdateUserUseCase(UserUseCase):
    async def execute(
        self,
        obj_data: UserUpdate,
        user_id: UUID,
        current_user: User,
        context: BaseContextKwargs | None = None,
    ) -> User | None:
        # A user may update their own record; updating anyone else requires superadmin.
        if current_user.id != user_id and not current_user.is_superadmin:
            raise PermissionDeniedException()
        async with self.transaction() as session:
            return await self.service.update_user(session, obj_data, user_id)
