"""
Service mixins that execute hooks.

Each service declares its hooks as one ordered ``hooks`` tuple. The executor
enters every relevant hook's context in that order, runs the repository call,
and unwinds in reverse -- so ``*_post`` hooks run in reverse declaration order,
mirroring the context exit order.

Hooks never call each other. Adding, reordering, or removing a hook cannot
silently disable another one.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from contextlib import AsyncExitStack
from dataclasses import replace
from functools import cached_property, lru_cache
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app_layer_base.base.repos.base import (
    BaseRepository,
    PrimaryKeyType,
)
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse, MultipleDeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from app_layer_base.base.services.hooks import (
    BaseContextKwargs,
    CreateHook,
    DeleteHook,
    GetHook,
    GetMultiHook,
    Operation,
    UpdateHook,
)
from app_layer_base.core.log import logger

__all__ = [
    "BaseContextKwargs",
    "BaseCreateServiceMixin",
    "BaseDeleteServiceMixin",
    "BaseGetMultiServiceMixin",
    "BaseGetServiceMixin",
    "BaseServiceMixinInterface",
    "BaseUpdateServiceMixin",
]


class BaseServiceMixinInterface[TContextKwargs: BaseContextKwargs]:
    """Base Service class."""

    hooks: Sequence[object] = ()
    """Ordered hooks for this service. Contexts are entered in this order and
    exited in reverse; ``*_post`` hooks likewise run in reverse."""

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

    # ------------------------------------------------------------------
    # Hook selection
    # ------------------------------------------------------------------

    @cached_property
    def create_hooks(self) -> tuple[CreateHook, ...]:
        return tuple(h for h in self.hooks if isinstance(h, CreateHook))

    @cached_property
    def update_hooks(self) -> tuple[UpdateHook, ...]:
        return tuple(h for h in self.hooks if isinstance(h, UpdateHook))

    @cached_property
    def delete_hooks(self) -> tuple[DeleteHook, ...]:
        return tuple(h for h in self.hooks if isinstance(h, DeleteHook))

    @cached_property
    def get_hooks(self) -> tuple[GetHook, ...]:
        return tuple(h for h in self.hooks if isinstance(h, GetHook))

    @cached_property
    def get_multi_hooks(self) -> tuple[GetMultiHook, ...]:
        return tuple(h for h in self.hooks if isinstance(h, GetMultiHook))

    # ------------------------------------------------------------------
    # Context handling
    # ------------------------------------------------------------------

    @classmethod
    @lru_cache
    def _get_adapter(cls, cast_to: Any) -> TypeAdapter[TContextKwargs]:
        """Get Pydantic TypeAdapter for the given context type."""
        return TypeAdapter(cast_to)

    @cached_property
    def _hook_context_keys_checked(self) -> bool:
        """
        Fail loudly (vs. silently no-op'ing) when a hook reads context keys the
        context model never declares: validation would drop (or, with
        ``extra="forbid"``, reject) them before the hook ever sees them.

        Runs once per service instance, on the first operation -- not in
        ``__init__``: the mixins do not own one (consumer services define their
        own without calling ``super().__init__()``), and services are
        request-scoped dependencies, so construction and first use coincide
        within the same request anyway.
        """
        model = self.context_model
        declared = getattr(model, "__required_keys__", frozenset()) | getattr(model, "__optional_keys__", frozenset())
        for hook in self.hooks:
            missing = frozenset(getattr(hook, "required_context_keys", ())) - declared
            if missing:
                raise TypeError(
                    f"{type(self).__name__}.context_model ({model.__name__}) does not declare "
                    f"context key(s) {sorted(missing)} required by {type(hook).__name__}. "
                    "Declare them on the context model (Required or NotRequired); otherwise "
                    "context validation drops them and the hook silently no-ops."
                )
        return True

    @classmethod
    def _ensure_context(
        cls,
        context: TContextKwargs | None,
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

    def _new_operation(self, session: AsyncSession, context: TContextKwargs | None) -> Operation[TContextKwargs]:
        _ = self._hook_context_keys_checked
        return Operation(
            session=session,
            context=self._ensure_context(context, self.context_model),
            repo=self.repo,
        )


# ============================================================
# Create
# ============================================================


class BaseCreateServiceMixin[
    TRepo: BaseRepository,
    ModelType,
    CreateSchemaType: BaseModel,
    TContextKwargs: BaseContextKwargs,
](
    ABC,
    BaseServiceMixinInterface[TContextKwargs],
):
    """
    Create operation Mixin.

    Usage:
        await service.create(session, obj_data, context={})
    """

    async def create(
        self,
        session: AsyncSession,
        obj_data: CreateSchemaType,
        context: TContextKwargs | None = None,
        **update_fields: Any,
    ) -> ModelType:
        op = self._new_operation(session, context)
        hooks = self.create_hooks

        async with AsyncExitStack() as stack:
            for hook in hooks:
                await stack.enter_async_context(hook.create_context(op, obj_data))

            fields = dict(update_fields)
            for hook in hooks:
                fields = hook.create_prepare_fields(op, obj_data, fields)

            obj = await self.repo.create(session, obj_in=obj_data, **fields)

            for hook in reversed(hooks):
                obj = await hook.create_post(op, obj)
            return obj

    async def create_multi(
        self,
        session: AsyncSession,
        obj_data_list: Sequence[CreateSchemaType],
        context: TContextKwargs | None = None,
        **update_fields: Any,
    ) -> Sequence[ModelType]:
        op = self._new_operation(session, context)
        hooks = self.create_hooks

        async with AsyncExitStack() as stack:
            for hook in hooks:
                await stack.enter_async_context(hook.create_context_multi(op, obj_data_list))

            extra_fields_list = []
            for obj_data in obj_data_list:
                fields = dict(update_fields)
                for hook in hooks:
                    fields = hook.create_prepare_fields(op, obj_data, fields)
                extra_fields_list.append(fields)

            objs = await self.repo.create_multi(session, objs_in=obj_data_list, extra_fields_list=extra_fields_list)

            for hook in reversed(hooks):
                objs = await hook.create_post_multi(op, objs)
            return objs


# ============================================================
# Update
# ============================================================


class BaseUpdateServiceMixin[
    TRepo: BaseRepository,
    ModelType,
    PutSchemaType: BaseModel,
    PatchSchemaType: BaseModel,
    TContextKwargs: BaseContextKwargs,
](
    ABC,
    BaseServiceMixinInterface[TContextKwargs],
):
    """
    Update operation Mixin.

    Usage:
        await service.put(session, obj_pk, obj_data, context={})
        await service.patch(session, obj_pk, obj_data, context={})
    """

    async def put(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: PutSchemaType,
        context: TContextKwargs | None = None,
        **update_fields: Any,
    ) -> ModelType | None:
        """Full update (PUT) of an object."""
        return await self._update_internal(session, obj_pk, obj_data, partial=False, context=context, **update_fields)

    async def patch(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: PatchSchemaType,
        context: TContextKwargs | None = None,
        **update_fields: Any,
    ) -> ModelType | None:
        """Partial update (PATCH) of an object."""
        return await self._update_internal(session, obj_pk, obj_data, partial=True, context=context, **update_fields)

    async def _update_internal(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: PutSchemaType | PatchSchemaType,
        partial: bool,
        context: TContextKwargs | None = None,
        **update_fields: Any,
    ) -> ModelType | None:
        op = self._new_operation(session, context)
        hooks = self.update_hooks

        async with AsyncExitStack() as stack:
            for hook in hooks:
                await stack.enter_async_context(hook.update_context(op, obj_pk, obj_data, partial=partial))

            fields = dict(update_fields)
            for hook in hooks:
                fields = hook.update_prepare_fields(op, obj_data, fields, partial=partial)

            obj = await self.repo.update_by_pk(session, pk=obj_pk, obj_in=obj_data, partial=partial, **fields)

            for hook in reversed(hooks):
                obj = await hook.update_post(op, obj, partial=partial)
            return obj


# ============================================================
# Delete
# ============================================================


class BaseDeleteServiceMixin[TRepo: BaseRepository, ModelType, TContextKwargs: BaseContextKwargs](
    ABC,
    BaseServiceMixinInterface[TContextKwargs],
):
    """
    Delete operation Mixin.

    Usage:
        await service.delete(session, obj_pk, context={})
    """

    async def delete(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        context: TContextKwargs | None = None,
    ) -> DeleteResponse:
        op = self._new_operation(session, context)
        hooks = self.delete_hooks

        async with AsyncExitStack() as stack:
            for hook in hooks:
                await stack.enter_async_context(hook.delete_context(op, obj_pk))

            success = await self.repo.delete_by_pk(session, pk=obj_pk)
            result = DeleteResponse(success=success, identity=obj_pk)

            for hook in reversed(hooks):
                result = await hook.delete_post(op, obj_pk, result)
            return result

    async def delete_multi(
        self,
        session: AsyncSession,
        obj_pks: Sequence[PrimaryKeyType],
        context: TContextKwargs | None = None,
    ) -> MultipleDeleteResponse:
        op = self._new_operation(session, context)
        hooks = self.delete_hooks

        async with AsyncExitStack() as stack:
            for hook in hooks:
                await stack.enter_async_context(hook.delete_context_multi(op, obj_pks))

            deleted_count = await self.repo.delete_by_pk_multi(session, pks=obj_pks)
            # failed_count is derived from the aggregate count (no extra query); per-item
            # failure detail is left to consumers via a delete_post_multi override.
            result = MultipleDeleteResponse(
                deleted_count=deleted_count,
                failed_count=max(0, len(obj_pks) - deleted_count),
            )

            for hook in reversed(hooks):
                result = await hook.delete_post_multi(op, obj_pks, result)
            return result


# ============================================================
# Get (single)
# ============================================================


class BaseGetServiceMixin[TRepo: BaseRepository, ModelType, TContextKwargs: BaseContextKwargs](
    ABC,
    BaseServiceMixinInterface[TContextKwargs],
):
    """
    Get (single item) operation Mixin.

    Usage:
        await service.get(session, obj_pk, context={})
    """

    async def get(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        context: TContextKwargs | None = None,
    ) -> ModelType | None:
        op = self._new_operation(session, context)
        hooks = self.get_hooks

        async with AsyncExitStack() as stack:
            for hook in hooks:
                await stack.enter_async_context(hook.get_context(op, obj_pk))

            obj = await self.repo.get_by_pk(session, pk=obj_pk)

            for hook in reversed(hooks):
                obj = await hook.get_post(op, obj)
            return obj


# ============================================================
# Get Multi (list)
# ============================================================


class BaseGetMultiServiceMixin[TRepo: BaseRepository, ModelType, TContextKwargs: BaseContextKwargs](
    ABC,
    BaseServiceMixinInterface[TContextKwargs],
):
    """
    Get Multi (list) operation Mixin.

    Usage:
        await service.get_multi(session, query_options=ListQueryOptions(offset=0, limit=100), context={})
    """

    async def get_multi(
        self,
        session: AsyncSession,
        query_options: ListQueryOptions | None = None,
        context: TContextKwargs | None = None,
    ) -> PaginatedList[ModelType]:
        query_options = query_options or ListQueryOptions()
        op = self._new_operation(session, context)
        hooks = self.get_multi_hooks

        async with AsyncExitStack() as stack:
            for hook in hooks:
                await stack.enter_async_context(hook.get_multi_context(op))

            # Inside the contexts, like every other operation's *_prepare_* step:
            # a hook may set up in its context what it filters on here.
            extra_filters: list[Any] = []
            for hook in hooks:
                extra_filters.extend(hook.get_multi_prepare_filters(op))

            where = query_options.where
            if where is None:
                where = extra_filters
            elif isinstance(where, Sequence):
                where = list(where) + extra_filters
            elif extra_filters:
                where = [where, *extra_filters]

            result = await self.repo.get_multi(session, query_options=replace(query_options, where=where))

            for hook in reversed(hooks):
                result = await hook.get_multi_post(op, result)
            return result
