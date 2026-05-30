from abc import abstractmethod
from contextlib import asynccontextmanager
from typing import Any, Required

from app_layer_base.base.exceptions.basic import NotFoundException
from pydantic import BaseModel

from app_nosql_db.hooks.base import (
    BaseNoSQLContextKwargs,
    BaseNoSQLCreateHooks,
    BaseNoSQLDeleteHooks,
    BaseNoSQLGetHooks,
    BaseNoSQLGetMultiHooks,
    BaseNoSQLUpdateHooks,
)
from app_nosql_db.interface import NoSQLDBProvider
from app_nosql_db.repository import NoSQLRepository


class NoSQLNestedResourceContextKwargs(BaseNoSQLContextKwargs):
    """Hierarchical context kwargs for NoSQL."""

    parent_id: Required[str]


class NoSQLNestedResourceHooksMixin[
    ModelType: Any,
    TNoSQLNestedResourceContextKwargs: NoSQLNestedResourceContextKwargs,
](
    BaseNoSQLCreateHooks[ModelType, TNoSQLNestedResourceContextKwargs],
    BaseNoSQLUpdateHooks[ModelType, TNoSQLNestedResourceContextKwargs],
    BaseNoSQLGetHooks[ModelType, TNoSQLNestedResourceContextKwargs],
    BaseNoSQLGetMultiHooks[ModelType, TNoSQLNestedResourceContextKwargs],
    BaseNoSQLDeleteHooks[TNoSQLNestedResourceContextKwargs],
):
    @property
    @abstractmethod
    def parent_repo(self) -> NoSQLRepository:
        """The repository of the parent resource."""
        pass

    @property
    def fk_name(self) -> str:
        """The name of the field in the child document that references the parent."""
        return "parent_id"

    # ============================================================
    # Helpers
    # ============================================================

    async def _check_parent_exists(self, provider: NoSQLDBProvider, parent_id: str) -> None:
        """Check if parent exists, raise NotFoundException if not."""
        if not await self.parent_repo.exists(provider, parent_id):
            raise NotFoundException(log_message=f"Parent {self.parent_repo.model_repr(parent_id)} not found.")

    async def _ensure_ownership(self, provider: NoSQLDBProvider, document_id: str, parent_id: str):
        """
        Ensure the document belongs to the specific parent.
        """
        obj = await self.repo.get_by_id(provider, document_id)
        if not obj:
            return

        # Get the actual parent ID from the object
        obj_parent_id = getattr(obj, self.fk_name, None)

        if str(obj_parent_id) != str(parent_id):
            raise NotFoundException(
                log_message=f"{self.repo.model_repr(document_id)} does not belong to {self.parent_repo.model_repr(parent_id)}"
            )

    # ============================================================
    # Create Hooks
    # ============================================================

    @asynccontextmanager
    async def _context_create(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_data: BaseModel,
        context: TNoSQLNestedResourceContextKwargs,
    ):
        async with super()._context_create(provider, document_id, obj_data, context):
            parent_id = context["parent_id"]
            await self._check_parent_exists(provider, parent_id)
            yield

    def _prepare_create_fields(
        self, obj_data: BaseModel, context: TNoSQLNestedResourceContextKwargs, **update_fields: Any
    ) -> dict[str, Any]:
        """Inject parent_id into the creation data."""
        data = super()._prepare_create_fields(obj_data, context, **update_fields)
        data[self.fk_name] = context["parent_id"]
        return data

    # ============================================================
    # Get Multi (List) Hooks
    # ============================================================

    def _prepare_get_multi_filters(self, context: TNoSQLNestedResourceContextKwargs) -> list[tuple[str, str, Any]]:
        """Automatically filter by parent_id."""
        filters = super()._prepare_get_multi_filters(context)
        parent_id = context["parent_id"]
        filters.append((self.fk_name, "==", parent_id))
        return filters

    @asynccontextmanager
    async def _context_get_multi(self, provider: NoSQLDBProvider, context: TNoSQLNestedResourceContextKwargs):
        """Optionally check if parent exists before listing children."""
        async with super()._context_get_multi(provider, context):
            await self._check_parent_exists(provider, context["parent_id"])
            yield

    # ============================================================
    # Get (Single) Hooks
    # ============================================================

    @asynccontextmanager
    async def _context_get(
        self, provider: NoSQLDBProvider, document_id: str, context: TNoSQLNestedResourceContextKwargs
    ):
        """Ensure the requested document belongs to the parent context."""
        async with super()._context_get(provider, document_id, context):
            await self._ensure_ownership(provider, document_id, context["parent_id"])
            yield

    # ============================================================
    # Update Hooks
    # ============================================================

    @asynccontextmanager
    async def _context_update(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_data: BaseModel,
        context: TNoSQLNestedResourceContextKwargs,
        partial: bool = True,
    ):
        """Ensure the document being updated belongs to the parent context."""
        async with super()._context_update(provider, document_id, obj_data, context, partial):
            await self._ensure_ownership(provider, document_id, context["parent_id"])
            yield

    # ============================================================
    # Delete Hooks
    # ============================================================

    @asynccontextmanager
    async def _context_delete(
        self, provider: NoSQLDBProvider, document_id: str, context: TNoSQLNestedResourceContextKwargs
    ):
        """Ensure the document being deleted belongs to the parent context."""
        async with super()._context_delete(provider, document_id, context):
            await self._ensure_ownership(provider, document_id, context["parent_id"])
            yield
