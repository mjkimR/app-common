from contextlib import asynccontextmanager
from typing import Any

from pydantic import BaseModel

from app_nosql_db.exceptions import NotFoundException
from app_nosql_db.hooks.base import BaseNoSQLContextKwargs, BaseNoSQLDeleteHooks, BaseNoSQLUpdateHooks
from app_nosql_db.interface import NoSQLDBProvider


class NoSQLExistsCheckHooksMixin[ModelType: Any, TContextKwargs: BaseNoSQLContextKwargs](
    BaseNoSQLUpdateHooks[ModelType, TContextKwargs], BaseNoSQLDeleteHooks[TContextKwargs]
):
    @asynccontextmanager
    async def _context_update(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_data: BaseModel,
        context: TContextKwargs,
        partial: bool = True,
    ):
        if not await self.repo.exists(provider, document_id):
            raise NotFoundException(log_message=f"{self.repo.model_repr(document_id)} does not exist.")
        yield

    @asynccontextmanager
    async def _context_delete(self, provider: NoSQLDBProvider, document_id: str, context: TContextKwargs):
        if not await self.repo.exists(provider, document_id):
            raise NotFoundException(log_message=f"{self.repo.model_repr(document_id)} does not exist.")

        yield
