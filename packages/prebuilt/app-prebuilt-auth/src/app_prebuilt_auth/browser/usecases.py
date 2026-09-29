from typing import Annotated

from fastapi import Depends

from app_prebuilt_auth.user.database import UserTransaction, get_user_transaction
from app_prebuilt_auth.user.token_schemas import Token

from .services import BrowserSessionService, digest


class BrowserSessionUseCase:
    def __init__(
        self,
        service: Annotated[BrowserSessionService, Depends()],
        transaction: Annotated[UserTransaction, Depends(get_user_transaction)],
    ):
        self.service, self.transaction = service, transaction

    async def begin(self, tokens: Token, previous: str) -> str:
        async with self.transaction() as session:
            return await self.service.begin(session, tokens.refresh_token or "", previous)

    async def refresh(self, key: str) -> Token:
        async with self.transaction() as session:
            return await self.service.refresh(session, key)

    async def logout(self, key: str) -> None:
        async with self.transaction() as session:
            await self.service.repo.revoke(session, digest(key))
