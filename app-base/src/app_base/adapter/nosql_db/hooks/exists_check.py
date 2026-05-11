from contextlib import asynccontextmanager

from pydantic import BaseModel

from app_base.adapter.nosql_db.hooks.base import BaseNoSQLDeleteHooks, BaseNoSQLUpdateHooks, TContextKwargs
from app_base.adapter.nosql_db.interface import NoSQLDBProvider
from app_base.base.exceptions.basic import NotFoundException


class NoSQLExistsCheckHooksMixin(BaseNoSQLUpdateHooks, BaseNoSQLDeleteHooks):
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
