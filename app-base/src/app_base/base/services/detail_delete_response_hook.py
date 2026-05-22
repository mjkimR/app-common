from abc import abstractmethod
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app_base.base.repos.base import PrimaryKeyType
from app_base.base.schemas.delete_resp import DeleteResponse
from app_base.base.services.base import BaseContextKwargs, BaseDeleteHooks


class DetailDeleteResponseHookMixin[ModelType: Any, TContextKwargs: BaseContextKwargs](BaseDeleteHooks[TContextKwargs]):
    _delete_represent_text: str | None = None

    @abstractmethod
    def _parse_delete_represent_text(self, obj: ModelType) -> str:
        pass

    def _set_delete_represent_text(self, text: str) -> None:
        self._delete_represent_text = text

    @asynccontextmanager
    async def _context_delete(self, session: AsyncSession, obj_pk: PrimaryKeyType, context: TContextKwargs):
        async with super()._context_delete(session, obj_pk, context):
            obj = await self.repo.get_by_pk(session, pk=obj_pk)
            if obj:
                represent_text = self._parse_delete_represent_text(obj)
                self._set_delete_represent_text(represent_text)
            yield

    async def _post_delete(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        result: DeleteResponse,
        context: TContextKwargs,
    ) -> DeleteResponse:
        """Hook executed after delete."""
        result = await super()._post_delete(session, obj_pk, result, context)
        if self._delete_represent_text:
            result.representation = self._delete_represent_text
        return result
