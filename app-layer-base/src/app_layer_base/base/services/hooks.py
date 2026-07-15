"""
Hook protocols for service operations.

A hook implements only its own behaviour and never calls the next hook. The
service executor (see ``services/base.py``) owns the chain: it enters every
hook's context in declaration order, runs the repository call, then unwinds in
reverse. A hook therefore cannot break the chain for the hooks after it.

The bulk variants (``*_multi``) exist so a hook can replace *its own* per-item
behaviour with a single bulk query -- e.g. checking a parent row once instead of
once per item. Overriding a bulk method never affects the other hooks: the
executor asks each hook separately, and any hook that has not overridden the
bulk method still gets its single-item hook applied to every item.

Per-operation state belongs on ``Operation.state``, never on the hook instance:
hooks may be shared, and the per-item fallback reuses the same hook object for
every item.
"""

from collections.abc import AsyncGenerator, Sequence
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, ClassVar, TypedDict

from pydantic import BaseModel, ConfigDict, with_config
from sqlalchemy.ext.asyncio import AsyncSession

from app_layer_base.base.repos.base import BaseRepository, PrimaryKeyType
from app_layer_base.base.schemas.delete_resp import DeleteResponse, MultipleDeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList


@with_config(ConfigDict(extra="forbid"))
class BaseContextKwargs(TypedDict):
    """
    Base context kwargs (empty, for extension).

    ``extra="forbid"`` applies to every subclass: passing a context key the
    model does not declare raises at validation instead of being silently
    dropped -- a dropped key would make context-reading hooks (audit stamping,
    parent scoping) silently no-op.
    """


class BaseHook:
    """Behaviour shared by every hook protocol."""

    required_context_keys: ClassVar[frozenset[str]] = frozenset()
    """Context keys this hook reads from ``op.context``.

    The service's ``context_model`` must declare every one of them (as
    ``Required`` or ``NotRequired`` -- that choice decides whether callers may
    omit the key). An undeclared key would be dropped by context validation, so
    the hook would silently no-op; the service executor therefore fails fast
    with a ``TypeError`` on the first operation instead.
    """


@dataclass(slots=True)
class Operation[TContextKwargs: BaseContextKwargs]:
    """
    Everything a hook needs for one service call.

    ``state`` is scratch space scoped to a single service call. A hook that needs
    to carry a value from its context hook to its post hook must put it here --
    storing it on the hook instance leaks across calls and across items. For state
    that must outlive the service call and reach the transaction's commit, use
    ``register_after_commit`` instead (it is keyed on the session, not on ``state``).
    """

    session: AsyncSession
    context: TContextKwargs
    repo: BaseRepository
    state: dict[str, Any] = field(default_factory=dict)

    def register_after_commit(self, callback) -> None:
        """Queue a coroutine to run after this operation's transaction commits.

        The seam for at-most-once side effects triggered by a write -- publishing a
        domain event, invalidating a cache, sending a notification. Registering
        here (rather than awaiting the effect inline in a ``*_post`` hook) keeps it
        off the rolled-back path: it fires only if the transaction actually commits.
        Capture plain data in ``callback``, not ORM objects. For at-least-once
        delivery use an outbox instead. See
        ``app_layer_base.core.database.transaction.register_after_commit``.
        """
        # Local import: keep hook imports free of the database engine module.
        from app_layer_base.core.database.transaction import register_after_commit

        register_after_commit(self.session, callback)


# ============================================================
# Create
# ============================================================


class CreateHook[ModelType: Any, TContextKwargs: BaseContextKwargs](BaseHook):
    """Hook for create / create_multi."""

    @asynccontextmanager
    async def create_context(self, op: Operation[TContextKwargs], data: BaseModel) -> AsyncGenerator[None]:
        """Wraps the create. Validate before the yield, clean up after it."""
        yield

    def create_prepare_fields(
        self, op: Operation[TContextKwargs], data: BaseModel, fields: dict[str, Any]
    ) -> dict[str, Any]:
        """Add or rewrite the extra column values passed to ``repo.create``."""
        return fields

    async def create_post(self, op: Operation[TContextKwargs], obj: ModelType) -> ModelType:
        """Runs after the row is created, inside every hook's context."""
        return obj

    @asynccontextmanager
    async def create_context_multi(
        self, op: Operation[TContextKwargs], data_list: Sequence[BaseModel]
    ) -> AsyncGenerator[None]:
        """
        Bulk form of ``create_context``.

        The default applies this hook's own ``create_context`` to every item.
        Override only to replace that with a bulk-level equivalent.
        """
        async with AsyncExitStack() as stack:
            for data in data_list:
                await stack.enter_async_context(self.create_context(op, data))
            yield

    async def create_post_multi(self, op: Operation[TContextKwargs], objs: Sequence[ModelType]) -> Sequence[ModelType]:
        """
        Bulk form of ``create_post``.

        The default applies this hook's own ``create_post`` to every item.
        Override only to replace that with a bulk-level equivalent.
        """
        return [await self.create_post(op, obj) for obj in objs]


# ============================================================
# Update
# ============================================================


class UpdateHook[ModelType: Any, TContextKwargs: BaseContextKwargs](BaseHook):
    """Hook for put / patch."""

    @asynccontextmanager
    async def update_context(
        self,
        op: Operation[TContextKwargs],
        pk: PrimaryKeyType,
        data: BaseModel,
        partial: bool = True,
    ) -> AsyncGenerator[None]:
        """Wraps the update. Validate before the yield, clean up after it."""
        yield

    def update_prepare_fields(
        self,
        op: Operation[TContextKwargs],
        data: BaseModel,
        fields: dict[str, Any],
        partial: bool = True,
    ) -> dict[str, Any]:
        """Add or rewrite the extra column values passed to ``repo.update_by_pk``."""
        return fields

    async def update_post(
        self,
        op: Operation[TContextKwargs],
        obj: ModelType | None,
        partial: bool = True,
    ) -> ModelType | None:
        """Runs after the row is updated. ``obj`` is None when the row did not exist."""
        return obj


# ============================================================
# Delete
# ============================================================


class DeleteHook[TContextKwargs: BaseContextKwargs](BaseHook):
    """Hook for delete / delete_multi."""

    @asynccontextmanager
    async def delete_context(self, op: Operation[TContextKwargs], pk: PrimaryKeyType) -> AsyncGenerator[None]:
        """Wraps the delete. The row still exists before the yield, not after it."""
        yield

    async def delete_post(
        self, op: Operation[TContextKwargs], pk: PrimaryKeyType, result: DeleteResponse
    ) -> DeleteResponse:
        """Runs after the row is deleted, inside every hook's context."""
        return result

    @asynccontextmanager
    async def delete_context_multi(
        self, op: Operation[TContextKwargs], pks: Sequence[PrimaryKeyType]
    ) -> AsyncGenerator[None]:
        """
        Bulk form of ``delete_context``.

        The default applies this hook's own ``delete_context`` to every item.
        Override only to replace that with a bulk-level equivalent.
        """
        async with AsyncExitStack() as stack:
            for pk in pks:
                await stack.enter_async_context(self.delete_context(op, pk))
            yield

    async def delete_post_multi(
        self,
        op: Operation[TContextKwargs],
        pks: Sequence[PrimaryKeyType],
        result: MultipleDeleteResponse,
    ) -> MultipleDeleteResponse:
        """
        Bulk form of ``delete_post``.

        MultipleDeleteResponse carries no per-item outcome, so the default only
        applies this hook's ``delete_post`` per item when the count proves every
        requested pk was deleted. Override to handle partial success.
        """
        if result.deleted_count == len(pks):
            for pk in pks:
                await self.delete_post(op, pk, DeleteResponse(success=True, identity=pk))
        return result


# ============================================================
# Get (single)
# ============================================================


class GetHook[ModelType: Any, TContextKwargs: BaseContextKwargs](BaseHook):
    """Hook for get."""

    @asynccontextmanager
    async def get_context(self, op: Operation[TContextKwargs], pk: PrimaryKeyType) -> AsyncGenerator[None]:
        yield

    async def get_post(self, op: Operation[TContextKwargs], obj: ModelType | None) -> ModelType | None:
        return obj


# ============================================================
# Get multi (list)
# ============================================================


class GetMultiHook[ModelType: Any, TContextKwargs: BaseContextKwargs](BaseHook):
    """Hook for get_multi."""

    @asynccontextmanager
    async def get_multi_context(self, op: Operation[TContextKwargs]) -> AsyncGenerator[None]:
        yield

    def get_multi_prepare_filters(self, op: Operation[TContextKwargs]) -> list[Any]:
        """Extra WHERE conditions ANDed into the list query."""
        return []

    async def get_multi_post(
        self, op: Operation[TContextKwargs], result: PaginatedList[ModelType]
    ) -> PaginatedList[ModelType]:
        return result


__all__ = [
    "BaseContextKwargs",
    "BaseHook",
    "CreateHook",
    "DeleteHook",
    "GetHook",
    "GetMultiHook",
    "Operation",
    "UpdateHook",
]
