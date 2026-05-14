import uuid
from contextlib import asynccontextmanager
from typing import Sequence

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
        partial: bool = True,
    ):
        if not await self.repo.get_by_pk(session, obj_id):
            raise NotFoundException(log_message=f"{self.repo.model_repr(obj_id)} does not exist.")
        yield

    @asynccontextmanager
    async def _context_delete(self, session: AsyncSession, obj_id: uuid.UUID, context: TContextKwargs):
        async with super()._context_delete(session, obj_id, context):
            if await self.repo.get_by_pk(session, obj_id) is None:
                raise NotFoundException(log_message=f"{self.repo.model_repr(obj_id)} does not exist.")
            yield

    @asynccontextmanager
    async def _context_delete_multi(self, session: AsyncSession, obj_ids: Sequence[uuid.UUID], context: TContextKwargs):
        """Bulk existence check using a single IN query instead of N individual get_by_pk calls."""
        async with super()._context_delete_multi(session, obj_ids, context):
            if obj_ids:
                pk_col = self.repo.primary_keys[0]
                existing_objs = await self.repo.get_all(session, where=pk_col.in_(obj_ids))
                existing_ids = {getattr(obj, pk_col.key) for obj in existing_objs}
                missing = [obj_id for obj_id in obj_ids if obj_id not in existing_ids]
                if missing:
                    missing_reprs = ", ".join(self.repo.model_repr(obj_id) for obj_id in missing)
                    raise NotFoundException(log_message=f"The following objects do not exist: {missing_reprs}")
            yield
