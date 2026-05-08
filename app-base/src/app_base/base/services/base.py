import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import Any, Generic, Optional, Sequence, TypedDict, Union

from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from typing_extensions import TypeVar

from app_base.base.repos.base import (
    BaseRepository,
    CreateSchemaType,
    ModelType,
    PatchSchemaType,
    PutSchemaType,
)
from app_base.base.schemas.delete_resp import DeleteResponse
from app_base.base.schemas.paginated import PaginatedList
from app_base.core.log import logger


class BaseContextKwargs(TypedDict):
    """Base context kwargs (empty, for extension)."""

    pass


TRepo = TypeVar("TRepo", bound=BaseRepository)
TContextKwargs = TypeVar("TContextKwargs", bound=BaseContextKwargs, default=BaseContextKwargs)


class BaseHooksInterface:
    """Base Hooks Interface."""

    repo: BaseRepository


class BaseServiceMixinInterface:
    """Base Service class."""

    @property
    @abstractmethod
    def repo(self) -> BaseRepository:
        """Repository instance."""
        pass

    @property
    @abstractmethod
    def context_model(self) -> type[TContextKwargs]:
        """Pydantic model for context kwargs."""
        pass

    @classmethod
    @lru_cache
    def _get_adapter(cls, cast_to: Any) -> TypeAdapter[TContextKwargs]:
        """Get Pydantic TypeAdapter for the given context type."""
        return TypeAdapter(cast_to)

    @classmethod
    def _ensure_context(
        cls,
        context: Optional[TContextKwargs],
        cast_to: Any = BaseContextKwargs,
    ) -> TContextKwargs:
        """
        Ensure context is not None.

        If context is None, returns an empty dict cast to TContextKwargs.
        Note: If TContextKwargs has required fields, caller must provide a valid context.
        """
        _context = context if context is not None else {}
        try:
            if cast_to == BaseContextKwargs and context:
                logger.warning(
                    "Context model is BaseContextKwargs but context is provided.\n"
                    f"Consider defining a specific context model with required fields for {cls.__name__}."
                )

            adapter = cls._get_adapter(cast_to)
            return adapter.validate_python(_context)
        except ValidationError as e:
            raise ValueError(f"Invalid context provided: {e}") from e


# ============================================================
# Create Hooks & Mixin
# ============================================================


class BaseCreateHooks(BaseHooksInterface):
    """Hook methods for Create operations."""

    @asynccontextmanager
    async def _context_create(self, session: AsyncSession, obj_data: BaseModel, context: TContextKwargs):
        """Hook executed within a context before create (validation, cascade handling, etc.)."""
        yield

    def _prepare_create_fields(
        self, obj_data: BaseModel, context: TContextKwargs, **update_fields: Any
    ) -> dict[str, Any]:
        """Hook to prepare additional fields before create."""
        return update_fields

    async def _post_create(self, session: AsyncSession, obj: ModelType, context: TContextKwargs) -> ModelType:
        """Hook executed after create."""
        return obj


class BaseCreateServiceMixin(
    ABC,
    BaseCreateHooks,
    BaseServiceMixinInterface,
    Generic[TRepo, ModelType, CreateSchemaType, TContextKwargs],
):
    """
    Create operation Mixin with hooks.

    Usage:
        await service.create(session, obj_data, context={})
    """

    async def create(
        self,
        session: AsyncSession,
        obj_data: CreateSchemaType,
        context: Optional[TContextKwargs] = None,
        **update_fields: Any,
    ) -> ModelType:
        ctx = self._ensure_context(context, self.context_model)
        async with self._context_create(session, obj_data, context=ctx):
            extra_fields = self._prepare_create_fields(obj_data, context=ctx, **update_fields)
            obj = await self.repo.create(session, obj_in=obj_data, **extra_fields)
            return await self._post_create(session, obj, context=ctx)


# ============================================================
# Update Hooks & Mixin
# ============================================================


class BaseUpdateHooks(BaseHooksInterface):
    """Hook methods for Update operations."""

    @asynccontextmanager
    async def _context_update(
        self,
        session: AsyncSession,
        obj_id: uuid.UUID,
        obj_data: BaseModel,
        context: TContextKwargs,
        partial: bool = True,
    ):
        """Hook executed within a context before update (validation, cascade handling, etc.)."""
        yield

    def _prepare_update_fields(
        self, obj_data: BaseModel, context: TContextKwargs, partial: bool = True, **update_fields: Any
    ) -> dict[str, Any]:
        """Hook to prepare additional fields before update."""
        return update_fields

    async def _post_update(
        self, session: AsyncSession, obj: ModelType, context: TContextKwargs, partial: bool = True
    ) -> ModelType:
        """Hook executed after update."""
        return obj


class BaseUpdateServiceMixin(
    ABC,
    BaseUpdateHooks,
    BaseServiceMixinInterface,
    Generic[TRepo, ModelType, PutSchemaType, PatchSchemaType, TContextKwargs],
):
    """
    Update operation Mixin with hooks.

    Usage:
        await service.update(session, obj_id, obj_data, context={})
    """

    async def put(
        self,
        session: AsyncSession,
        obj_id: uuid.UUID,
        obj_data: PutSchemaType,
        context: Optional[TContextKwargs] = None,
        **update_fields: Any,
    ) -> ModelType | None:
        """Full update (PUT) of an object."""
        return await self._update_internal(session, obj_id, obj_data, partial=False, context=context, **update_fields)

    async def patch(
        self,
        session: AsyncSession,
        obj_id: uuid.UUID,
        obj_data: PatchSchemaType,
        context: Optional[TContextKwargs] = None,
        **update_fields: Any,
    ) -> ModelType | None:
        """Partial update (PATCH) of an object."""
        return await self._update_internal(session, obj_id, obj_data, partial=True, context=context, **update_fields)

    async def _update_internal(
        self,
        session: AsyncSession,
        obj_id: uuid.UUID,
        obj_data: Union[PutSchemaType, PatchSchemaType],
        partial: bool,
        context: Optional[TContextKwargs] = None,
        **update_fields: Any,
    ) -> ModelType | None:
        ctx = self._ensure_context(context, self.context_model)
        async with self._context_update(session, obj_id, obj_data, context=ctx, partial=partial):
            extra_fields = self._prepare_update_fields(obj_data, context=ctx, partial=partial, **update_fields)
            obj = await self.repo.update_by_pk(session, pk=obj_id, obj_in=obj_data, partial=partial, **extra_fields)
            return await self._post_update(session, obj, context=ctx, partial=partial)


# ============================================================
# Delete Hooks & Mixin
# ============================================================


class BaseDeleteHooks(BaseHooksInterface):
    """Hook methods for Delete operations."""

    @asynccontextmanager
    async def _context_delete(self, session: AsyncSession, obj_id: uuid.UUID, context: TContextKwargs):
        """Hook executed within a context before delete (validation, cascade handling, etc.)."""
        yield

    async def _post_delete(
        self,
        session: AsyncSession,
        obj_id: uuid.UUID,
        result: DeleteResponse,
        context: TContextKwargs,
    ) -> DeleteResponse:
        """Hook executed after delete."""
        return result


class BaseDeleteServiceMixin(
    ABC,
    BaseDeleteHooks,
    BaseServiceMixinInterface,
    Generic[TRepo, ModelType, TContextKwargs],
):
    """
    Delete operation Mixin with hooks.

    Usage:
        await service.delete(session, obj_id, context={})
    """

    async def delete(
        self,
        session: AsyncSession,
        obj_id: uuid.UUID,
        context: Optional[TContextKwargs] = None,
    ) -> DeleteResponse:
        ctx = self._ensure_context(context, self.context_model)
        async with self._context_delete(session, obj_id, context=ctx):
            success = await self.repo.delete_by_pk(session, pk=obj_id)
            result = DeleteResponse(success=success, identity=obj_id)
            result = await self._post_delete(session, obj_id, result, context=ctx)
            return result


# ============================================================
# Get (Single) Hooks & Mixin
# ============================================================


class BaseGetHooks(BaseHooksInterface):
    """Hook methods for Get (single item) operations."""

    @asynccontextmanager
    async def _context_get(self, session: AsyncSession, obj_id: uuid.UUID, context: TContextKwargs):
        """Hook executed within a context before get (validation, cascade handling, etc.)."""
        yield

    async def _post_get(
        self, session: AsyncSession, obj: ModelType | None, context: TContextKwargs
    ) -> ModelType | None:
        """Hook executed after get (data transformation, etc.)."""
        return obj


class BaseGetServiceMixin(
    ABC,
    BaseGetHooks,
    BaseServiceMixinInterface,
    Generic[TRepo, ModelType, TContextKwargs],
):
    """
    Get (single item) operation Mixin with hooks.

    Usage:
        await service.get(session, obj_id, context={})
    """

    async def get(
        self,
        session: AsyncSession,
        obj_id: uuid.UUID,
        context: Optional[TContextKwargs] = None,
    ) -> ModelType | None:
        ctx = self._ensure_context(context, self.context_model)
        async with self._context_get(session, obj_id, context=ctx):
            obj = await self.repo.get_by_pk(session, pk=obj_id)
            return await self._post_get(session, obj, context=ctx)


# ============================================================
# Get Multi (List) Hooks & Mixin
# ============================================================


class BaseGetMultiHooks(BaseHooksInterface):
    """Hook methods for Get Multi (list) operations."""

    @asynccontextmanager
    async def _context_get_multi(self, session: AsyncSession, context: TContextKwargs):
        """Hook executed within a context before get multi (data transformation, etc.)."""
        yield

    def _prepare_get_multi_filters(self, context: TContextKwargs) -> list[Any]:
        """Hook to prepare additional filter conditions for list queries."""
        return []

    async def _post_get_multi(
        self,
        session: AsyncSession,
        result: PaginatedList[ModelType],
        context: TContextKwargs,
    ) -> PaginatedList[ModelType]:
        """Hook executed after get multi (data transformation, etc.)."""
        return result


class BaseGetMultiServiceMixin(
    ABC,
    BaseGetMultiHooks,
    BaseServiceMixinInterface,
    Generic[TRepo, ModelType, TContextKwargs],
):
    """
    Get Multi (list) operation Mixin with hooks.

    Usage:
        await service.get_multi(session, offset=0, limit=100, context={})
    """

    async def get_multi(
        self,
        session: AsyncSession,
        offset: int = 0,
        limit: Optional[int] = 100,
        order_by=(),
        where=(),
        context: Optional[TContextKwargs] = None,
    ) -> PaginatedList[ModelType]:
        ctx = self._ensure_context(context, self.context_model)
        async with self._context_get_multi(session, context=ctx):
            extra_filters = self._prepare_get_multi_filters(context=ctx)

            # Merge where conditions
            if where is None:
                where = extra_filters
            elif isinstance(where, Sequence):
                where = list(where) + extra_filters
            elif extra_filters:
                where = [where] + extra_filters

            result = await self.repo.get_multi(session, offset=offset, limit=limit, where=where, order_by=order_by)
            return await self._post_get_multi(session, result, context=ctx)
