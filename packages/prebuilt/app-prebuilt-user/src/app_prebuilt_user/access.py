from typing import Annotated
from uuid import UUID

from fastapi import Depends

from .access_service import AccessService
from .database import UserTransaction, get_user_transaction
from .schemas import UserAccessChange, UserAccessEventRead, UserReadAdmin


class AccessUseCase:
    def __init__(
        self,
        service: Annotated[AccessService, Depends()],
        transaction: Annotated[UserTransaction, Depends(get_user_transaction)],
    ):
        self.service = service
        self.transaction = transaction

    async def change(self, user_id: UUID, data: UserAccessChange, actor_id: UUID) -> UserReadAdmin:
        async with self.transaction() as session:
            return UserReadAdmin.model_validate(await self.service.change(session, user_id, data, actor_id))

    async def events(self, user_id: UUID) -> list[UserAccessEventRead]:
        async with self.transaction() as session:
            return [
                UserAccessEventRead.model_validate(event) for event in await self.service.repo.events(session, user_id)
            ]
