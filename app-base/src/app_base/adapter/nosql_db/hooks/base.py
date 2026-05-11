from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, Generic, Optional, TypedDict, Union

from pydantic import BaseModel, TypeAdapter, ValidationError
from typing_extensions import TypeVar

from app_base.adapter.nosql_db.interface import NoSQLDBProvider
from app_base.adapter.nosql_db.repository import (
    CreateSchemaType,
    ModelType,
    NoSQLRepository,
    PatchSchemaType,
    PutSchemaType,
)
from app_base.base.schemas.delete_resp import DeleteResponse
from app_base.base.schemas.paginated import PaginatedList

# Backward compatibility alias
UpdateSchemaType = PutSchemaType


class BaseNoSQLContextKwargs(TypedDict):
    """Base NoSQL context kwargs."""

    pass


TNoSQLRepo = TypeVar("TNoSQLRepo", bound=NoSQLRepository)
TContextKwargs = TypeVar("TContextKwargs", bound=BaseNoSQLContextKwargs, default=BaseNoSQLContextKwargs)


class BaseNoSQLHooksInterface:
    """Base NoSQL Hooks Interface."""

    repo: NoSQLRepository


class BaseNoSQLServiceMixinInterface:
    """Base NoSQL Service class."""

    @property
    @abstractmethod
    def repo(self) -> NoSQLRepository:
        pass

    @property
    @abstractmethod
    def context_model(self) -> type[TContextKwargs]:
        pass

    @classmethod
    @lru_cache
    def _get_adapter(cls, cast_to: Any) -> TypeAdapter[TContextKwargs]:
        return TypeAdapter(cast_to)

    @classmethod
    def _ensure_context(
        cls,
        context: Optional[TContextKwargs],
        cast_to: Any = BaseNoSQLContextKwargs,
    ) -> TContextKwargs:
        _context = context if context is not None else {}
        try:
            adapter = cls._get_adapter(cast_to)
            return adapter.validate_python(_context)
        except ValidationError as e:
            raise ValueError(f"Invalid context provided: {e}") from e


# ============================================================
# Create Hooks & Mixin
# ============================================================


class BaseNoSQLCreateHooks(BaseNoSQLHooksInterface):
    @asynccontextmanager
    async def _context_create(
        self, provider: NoSQLDBProvider, document_id: str, obj_data: BaseModel, context: TContextKwargs
    ):
        yield

    def _prepare_create_fields(
        self, obj_data: BaseModel, context: TContextKwargs, **update_fields: Any
    ) -> dict[str, Any]:
        return update_fields

    async def _post_create(self, provider: NoSQLDBProvider, obj: ModelType, context: TContextKwargs) -> ModelType:
        return obj


class BaseNoSQLCreateServiceMixin(
    ABC,
    BaseNoSQLCreateHooks,
    BaseNoSQLServiceMixinInterface,
    Generic[TNoSQLRepo, ModelType, CreateSchemaType, TContextKwargs],
):
    async def create(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_data: CreateSchemaType,
        context: Optional[TContextKwargs] = None,
        **update_fields: Any,
    ) -> ModelType:
        ctx = self._ensure_context(context, self.context_model)
        async with self._context_create(provider, document_id, obj_data, context=ctx):
            extra_fields = self._prepare_create_fields(obj_data, context=ctx, **update_fields)
            obj = await self.repo.create(provider, document_id=document_id, obj_in=obj_data, **extra_fields)
            return await self._post_create(provider, obj, context=ctx)


# ============================================================
# Update Hooks & Mixin
# ============================================================


class BaseNoSQLUpdateHooks(BaseNoSQLHooksInterface):
    @asynccontextmanager
    async def _context_update(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_data: BaseModel,
        context: TContextKwargs,
        partial: bool = True,
    ):
        yield

    def _prepare_update_fields(
        self, obj_data: BaseModel, context: TContextKwargs, partial: bool = True, **update_fields: Any
    ) -> dict[str, Any]:
        return update_fields

    async def _post_update(
        self, provider: NoSQLDBProvider, obj: ModelType, context: TContextKwargs, partial: bool = True
    ) -> ModelType:
        return obj


class BaseNoSQLUpdateServiceMixin(
    ABC,
    BaseNoSQLUpdateHooks,
    BaseNoSQLServiceMixinInterface,
    Generic[TNoSQLRepo, ModelType, PutSchemaType, PatchSchemaType, TContextKwargs],
):
    async def put(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_data: PutSchemaType,
        context: Optional[TContextKwargs] = None,
        **update_fields: Any,
    ) -> ModelType | None:
        """Full update (PUT) of a document."""
        return await self._update_internal(
            provider, document_id, obj_data, partial=False, context=context, **update_fields
        )

    async def patch(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_data: PatchSchemaType,
        context: Optional[TContextKwargs] = None,
        **update_fields: Any,
    ) -> ModelType | None:
        """Partial update (PATCH) of a document."""
        return await self._update_internal(
            provider, document_id, obj_data, partial=True, context=context, **update_fields
        )

    async def _update_internal(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_data: Union[PutSchemaType, PatchSchemaType],
        partial: bool,
        context: Optional[TContextKwargs] = None,
        **update_fields: Any,
    ) -> ModelType | None:
        ctx = self._ensure_context(context, self.context_model)
        async with self._context_update(provider, document_id, obj_data, context=ctx, partial=partial):
            extra_fields = self._prepare_update_fields(obj_data, context=ctx, partial=partial, **update_fields)
            if partial:
                obj = await self.repo.patch(provider, document_id=document_id, obj_in=obj_data, **extra_fields)
            else:
                obj = await self.repo.put(provider, document_id=document_id, obj_in=obj_data, **extra_fields)
            return await self._post_update(provider, obj, context=ctx, partial=partial)


# ============================================================
# Delete Hooks & Mixin
# ============================================================


class BaseNoSQLDeleteHooks(BaseNoSQLHooksInterface):
    @asynccontextmanager
    async def _context_delete(self, provider: NoSQLDBProvider, document_id: str, context: TContextKwargs):
        yield

    async def _post_delete(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        result: DeleteResponse,
        context: TContextKwargs,
    ) -> DeleteResponse:
        return result


class BaseNoSQLDeleteServiceMixin(
    ABC,
    BaseNoSQLDeleteHooks,
    BaseNoSQLServiceMixinInterface,
    Generic[TNoSQLRepo, ModelType, TContextKwargs],
):
    async def delete(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        context: Optional[TContextKwargs] = None,
    ) -> DeleteResponse:
        ctx = self._ensure_context(context, self.context_model)
        async with self._context_delete(provider, document_id, context=ctx):
            success = await self.repo.delete(provider, document_id=document_id)
            result = DeleteResponse(success=success, identity=document_id)
            result = await self._post_delete(provider, document_id, result, context=ctx)
            return result


# ============================================================
# Get (Single) Hooks & Mixin
# ============================================================


class BaseNoSQLGetHooks(BaseNoSQLHooksInterface):
    @asynccontextmanager
    async def _context_get(self, provider: NoSQLDBProvider, document_id: str, context: TContextKwargs):
        yield

    async def _post_get(
        self, provider: NoSQLDBProvider, obj: ModelType | None, context: TContextKwargs
    ) -> ModelType | None:
        return obj


class BaseNoSQLGetServiceMixin(
    ABC,
    BaseNoSQLGetHooks,
    BaseNoSQLServiceMixinInterface,
    Generic[TNoSQLRepo, ModelType, TContextKwargs],
):
    async def get(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        context: Optional[TContextKwargs] = None,
    ) -> ModelType | None:
        ctx = self._ensure_context(context, self.context_model)
        async with self._context_get(provider, document_id, context=ctx):
            obj = await self.repo.get_by_id(provider, document_id=document_id)
            return await self._post_get(provider, obj, context=ctx)


# ============================================================
# Get Multi (List) Hooks & Mixin
# ============================================================


class BaseNoSQLGetMultiHooks(BaseNoSQLHooksInterface):
    @asynccontextmanager
    async def _context_get_multi(self, provider: NoSQLDBProvider, context: TContextKwargs):
        yield

    def _prepare_get_multi_filters(self, context: TContextKwargs) -> list[tuple[str, str, Any]]:
        return []

    async def _post_get_multi(
        self,
        provider: NoSQLDBProvider,
        result: PaginatedList[ModelType],
        context: TContextKwargs,
    ) -> PaginatedList[ModelType]:
        return result


class BaseNoSQLGetMultiServiceMixin(
    ABC,
    BaseNoSQLGetMultiHooks,
    BaseNoSQLServiceMixinInterface,
    Generic[TNoSQLRepo, ModelType, TContextKwargs],
):
    async def get_multi(
        self,
        provider: NoSQLDBProvider,
        offset: int = 0,
        limit: int = 100,
        filters: list[tuple[str, str, Any]] | None = None,
        context: Optional[TContextKwargs] = None,
    ) -> PaginatedList[ModelType]:
        ctx = self._ensure_context(context, self.context_model)
        async with self._context_get_multi(provider, context=ctx):
            extra_filters = self._prepare_get_multi_filters(context=ctx)
            all_filters = (filters or []) + extra_filters
            result = await self.repo.get_multi(provider, filters=all_filters, offset=offset, limit=limit)
            return await self._post_get_multi(provider, result, context=ctx)
