from typing import Annotated

from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends

from app_prebuilt_user.models import User
from app_prebuilt_user.services import UserService


class AuthenticateUserUseCase(BaseUseCase):
    def __init__(self, service: Annotated[UserService, Depends()]):
        self.service = service

    async def execute(self, email: str, password: str) -> User | None:
        # Commit an upgraded password hash before issuing tokens tied to that hash.
        async with AsyncTransaction() as session:
            user = await self.service.authenticate(session, email=email, password=password)
        return user
