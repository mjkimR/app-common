from typing import Annotated

from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction
from fastapi import Depends

from ..database import UserTransaction, get_user_transaction
from ..services import UserService


class UserUseCase(BaseUseCase):
    def __init__(
        self,
        service: Annotated[UserService, Depends()],
        transaction: Annotated[UserTransaction, Depends(get_user_transaction)] = AsyncTransaction,
    ):
        self.service = service
        self.transaction = transaction
