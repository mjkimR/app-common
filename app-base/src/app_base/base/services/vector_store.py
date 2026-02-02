from abc import abstractmethod

from langchain_core.vectorstores import VectorStore
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app_base.base.services.base import BaseCreateHooks, BaseDeleteHooks, BaseUpdateHooks, TContextKwargs


class VectorStoreHookMixin(
    BaseCreateHooks,
    BaseUpdateHooks,
    BaseDeleteHooks,
):
    @property
    @abstractmethod
    def vector_store(self) -> VectorStore:
        """Vector store instance associated with the service."""
        pass

    async def _context_create(self, session: AsyncSession, obj_data: BaseModel, context: TContextKwargs):
        async with super()._context_create(session, obj_data, context):
            yield


class SearchServiceMixin:
    pass
