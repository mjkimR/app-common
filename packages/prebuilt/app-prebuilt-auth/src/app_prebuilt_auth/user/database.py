from collections.abc import Callable
from contextlib import AbstractAsyncContextManager

from app_layer_base.core.database.transaction import AsyncTransaction
from sqlalchemy.ext.asyncio import AsyncSession

UserTransaction = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def get_user_transaction() -> UserTransaction:
    """Override to use the host's session maker; every usecase owns its transaction."""
    return AsyncTransaction
