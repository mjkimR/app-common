from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import replace
from functools import lru_cache
from typing import Any, TypedDict

from pydantic import BaseModel, TypeAdapter, ValidationError

from app_base.adapter.nosql_db.interface import NoSQLDBProvider
from app_base.adapter.nosql_db.query_options import NoSQLListQueryOptions
from app_base.adapter.nosql_db.repository import NoSQLRepository
from app_base.base.schemas.delete_resp import DeleteResponse
from app_base.base.schemas.paginated import PaginatedList


class BaseNoSQLContextKwargs(TypedDict):
    """Base NoSQL context kwargs."""

    pass


class BaseNoSQLHooksInterface:
    """Base NoSQL Hooks Interface."""

    repo: NoSQLRepository


class BaseNoSQLServiceMixinInterface[TContextKwargs: BaseNoSQLContextKwargs]:
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
        context: TContextKwargs | None,
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


class BaseNoSQLCreateHooks[ModelType: Any, TContextKwargs: BaseNoSQLContextKwargs](BaseNoSQLHooksInterface):
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


class BaseNoSQLCreateServiceMixin[
    TNoSQLRepo: NoSQLRepository,
    ModelType: Any,
    CreateSchemaType: BaseModel,
    TContextKwargs: BaseNoSQLContextKwargs,
](
    ABC,
    BaseNoSQLCreateHooks[ModelType, TContextKwargs],
    BaseNoSQLServiceMixinInterface[TContextKwargs],
):
    async def create(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_data: CreateSchemaType,
        context: TContextKwargs | None = None,
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


class BaseNoSQLUpdateHooks[ModelType: Any, TContextKwargs: BaseNoSQLContextKwargs](BaseNoSQLHooksInterface):
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


class BaseNoSQLUpdateServiceMixin[
    TNoSQLRepo: NoSQLRepository,
    ModelType: Any,
    PutSchema: BaseModel,
    PatchSchema: BaseModel,
    TContextKwargs: BaseNoSQLContextKwargs,
](
    ABC,
    BaseNoSQLUpdateHooks[ModelType, TContextKwargs],
    BaseNoSQLServiceMixinInterface[TContextKwargs],
):
    async def put(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_data: PutSchema,
        context: TContextKwargs | None = None,
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
        obj_data: PatchSchema,
        context: TContextKwargs | None = None,
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
        obj_data: PutSchema | PatchSchema,
        partial: bool,
        context: TContextKwargs | None = None,
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


class BaseNoSQLDeleteHooks[TContextKwargs: BaseNoSQLContextKwargs](BaseNoSQLHooksInterface):
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


class BaseNoSQLDeleteServiceMixin[TNoSQLRepo: NoSQLRepository, ModelType: Any, TContextKwargs: BaseNoSQLContextKwargs](
    ABC,
    BaseNoSQLDeleteHooks[TContextKwargs],
    BaseNoSQLServiceMixinInterface[TContextKwargs],
):
    async def delete(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        context: TContextKwargs | None = None,
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


class BaseNoSQLGetHooks[ModelType: Any, TContextKwargs: BaseNoSQLContextKwargs](BaseNoSQLHooksInterface):
    @asynccontextmanager
    async def _context_get(self, provider: NoSQLDBProvider, document_id: str, context: TContextKwargs):
        yield

    async def _post_get(
        self, provider: NoSQLDBProvider, obj: ModelType | None, context: TContextKwargs
    ) -> ModelType | None:
        return obj


class BaseNoSQLGetServiceMixin[TNoSQLRepo: NoSQLRepository, ModelType: Any, TContextKwargs: BaseNoSQLContextKwargs](
    ABC,
    BaseNoSQLGetHooks[ModelType, TContextKwargs],
    BaseNoSQLServiceMixinInterface[TContextKwargs],
):
    async def get(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        context: TContextKwargs | None = None,
    ) -> ModelType | None:
        ctx = self._ensure_context(context, self.context_model)
        async with self._context_get(provider, document_id, context=ctx):
            obj = await self.repo.get_by_id(provider, document_id=document_id)
            return await self._post_get(provider, obj, context=ctx)


# ============================================================
# Get Multi (List) Hooks & Mixin
# ============================================================


class BaseNoSQLGetMultiHooks[ModelType: Any, TContextKwargs: BaseNoSQLContextKwargs](BaseNoSQLHooksInterface):
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


class BaseNoSQLGetMultiServiceMixin[
    TNoSQLRepo: NoSQLRepository,
    ModelType: Any,
    TContextKwargs: BaseNoSQLContextKwargs,
](
    ABC,
    BaseNoSQLGetMultiHooks[ModelType, TContextKwargs],
    BaseNoSQLServiceMixinInterface[TContextKwargs],
):
    async def get_multi(
        self,
        provider: NoSQLDBProvider,
        query_options: NoSQLListQueryOptions | None = None,
        context: TContextKwargs | None = None,
    ) -> PaginatedList[ModelType]:
        query_options = query_options or NoSQLListQueryOptions()
        ctx = self._ensure_context(context, self.context_model)
        async with self._context_get_multi(provider, context=ctx):
            extra_filters = self._prepare_get_multi_filters(context=ctx)
            query_options = replace(query_options, filters=[*query_options.filters, *extra_filters])
            result = await self.repo.get_multi(provider, query_options=query_options)
            return await self._post_get_multi(provider, result, context=ctx)
