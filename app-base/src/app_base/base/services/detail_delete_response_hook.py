import uuid
from abc import abstractmethod
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app_base.base.schemas.delete_resp import DeleteResponse
from app_base.base.services.base import BaseDeleteHooks, TContextKwargs


class DetailDeleteResponseHookMixin(BaseDeleteHooks):
    _delete_represent_text: str | None = None

    @abstractmethod
    def _parse_delete_represent_text(self, obj: Any) -> str:
        pass

    def _set_delete_represent_text(self, text: str) -> None:
        self._delete_represent_text = text

    @asynccontextmanager
    async def _context_delete(self, session: AsyncSession, obj_id: uuid.UUID, context: TContextKwargs):
        async with super()._context_delete(session, obj_id, context):
            obj = await self.repo.get_by_pk(session, pk=obj_id)
            if obj:
                represent_text = self._parse_delete_represent_text(obj)
                self._set_delete_represent_text(represent_text)
            yield

    async def _post_delete(
        self,
        session: AsyncSession,
        obj_id: uuid.UUID,
        result: DeleteResponse,
        context: TContextKwargs,
    ) -> DeleteResponse:
        """Hook executed after delete."""
        result = await super()._post_delete(session, obj_id, result, context)
        if self._delete_represent_text:
            result.representation = self._delete_represent_text
        return result
