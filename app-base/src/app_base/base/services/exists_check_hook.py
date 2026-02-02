import uuid
from contextlib import asynccontextmanager

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app_base.base.exceptions.basic import NotFoundException
from app_base.base.services.base import BaseDeleteHooks, BaseUpdateHooks, TContextKwargs


class ExistsCheckHooksMixin(BaseUpdateHooks, BaseDeleteHooks):
    @asynccontextmanager
    async def _context_update(
        self,
        session: AsyncSession,
        obj_id: uuid.UUID,
        obj_data: BaseModel,
        context: TContextKwargs,
    ):
        if not await self.repo.get_by_pk(session, obj_id):
            raise NotFoundException(log_message=f"{self.repo.model_repr(obj_id)} does not exist.")
        yield

    @asynccontextmanager
    async def _context_delete(self, session: AsyncSession, obj_id: uuid.UUID, context: TContextKwargs):
        if await self.repo.get_by_pk(session, obj_id) is None:
            raise NotFoundException(log_message=f"{self.repo.model_repr(obj_id)} does not exist.")

        yield
