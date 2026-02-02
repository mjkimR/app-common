import uuid
from abc import abstractmethod
from contextlib import asynccontextmanager
from typing import Any, Required

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app_base.base.exceptions.basic import NotFoundException
from app_base.base.repos.base import BaseRepository
from app_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateHooks,
    BaseDeleteHooks,
    BaseGetHooks,
    BaseGetMultiHooks,
    BaseUpdateHooks,
    TContextKwargs,
)


class NestedResourceContextKwargs(BaseContextKwargs):
    """Hierarchical context kwargs."""

    parent_id: Required[uuid.UUID]


class NestedResourceHooksMixin(
    BaseCreateHooks,
    BaseUpdateHooks,
    BaseGetHooks,
    BaseGetMultiHooks,
    BaseDeleteHooks,
):
    @property
    @abstractmethod
    def parent_repo(self) -> BaseRepository:
        """The repository of the parent resource."""
        pass

    @property
    def fk_name(self) -> str:
        """The name of the foreign key field in the child model that references the parent."""
        return "parent_id"

    # ============================================================
    # Helpers
    # ============================================================

    async def _check_parent_exists(self, session: AsyncSession, parent_id: Any) -> None:
        """Check if parent exists, raise NotFoundException if not."""
        #
        if not await self.parent_repo.get_by_pk(session, parent_id):
            raise NotFoundException(log_message=f"Parent {self.parent_repo.model_repr(parent_id)} not found.")

    async def _ensure_ownership(self, session: AsyncSession, obj_id: uuid.UUID, parent_id: Any):
        """
        Ensure the object belongs to the specific parent.
        This prevents accessing/modifying a child object through a wrong parent URL.
        """
        obj = await self.repo.get_by_pk(session, obj_id)
        if not obj:
            return

        # Get the actual parent ID from the object
        obj_parent_id = getattr(obj, self.fk_name)

        # Compare as strings to avoid type mismatches
        if str(obj_parent_id) != str(parent_id):
            raise NotFoundException(
                log_message=f"{self.repo.model_repr(obj_id)} does not belong to {self.parent_repo.model_repr(parent_id)}"
            )

    # ============================================================
    # Create Hooks
    # ============================================================

    @asynccontextmanager
    async def _context_create(self, session: AsyncSession, obj_data: BaseModel, context: TContextKwargs):
        async with super()._context_create(session, obj_data, context):
            parent_id = context["parent_id"]
            await self._check_parent_exists(session, parent_id)
            yield

    def _prepare_create_fields(self, obj_data: BaseModel, context: TContextKwargs) -> dict[str, Any]:
        """Inject parent_id into the creation data."""
        data = super()._prepare_create_fields(obj_data, context)
        data[self.fk_name] = context["parent_id"]
        return data

    # ============================================================
    # Get Multi (List) Hooks
    # ============================================================

    def _prepare_get_multi_filters(self, context: TContextKwargs) -> list[Any]:
        """Automatically filter by parent_id."""
        filters = super()._prepare_get_multi_filters(context)

        parent_id = context["parent_id"]
        filters.append(getattr(self.repo.model, self.fk_name) == parent_id)

        return filters

    @asynccontextmanager
    async def _context_get_multi(self, session: AsyncSession, context: TContextKwargs):
        """Optionally check if parent exists before listing children."""
        async with super()._context_get_multi(session, context):
            # Optional: Fail fast if parent doesn't exist, even if list would just be empty.
            await self._check_parent_exists(session, context["parent_id"])
            yield

    # ============================================================
    # Get (Single) Hooks
    # ============================================================

    @asynccontextmanager
    async def _context_get(self, session: AsyncSession, obj_id: uuid.UUID, context: TContextKwargs):
        """Ensure the requested object belongs to the parent context."""
        async with super()._context_get(session, obj_id, context):
            await self._ensure_ownership(session, obj_id, context["parent_id"])
            yield

    # ============================================================
    # Update Hooks
    # ============================================================

    @asynccontextmanager
    async def _context_update(
        self,
        session: AsyncSession,
        obj_id: uuid.UUID,
        obj_data: BaseModel,
        context: TContextKwargs,
    ):
        """Ensure the object being updated belongs to the parent context."""
        async with super()._context_update(session, obj_id, obj_data, context):
            await self._ensure_ownership(session, obj_id, context["parent_id"])
            yield

    # ============================================================
    # Delete Hooks
    # ============================================================

    @asynccontextmanager
    async def _context_delete(self, session: AsyncSession, obj_id: uuid.UUID, context: TContextKwargs):
        """Ensure the object being deleted belongs to the parent context."""
        async with super()._context_delete(session, obj_id, context):
            await self._ensure_ownership(session, obj_id, context["parent_id"])
            yield
