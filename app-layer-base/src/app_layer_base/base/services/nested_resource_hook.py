from abc import abstractmethod
from collections.abc import Sequence
from contextlib import asynccontextmanager
from typing import Any, Required

from pydantic import BaseModel
from sqlalchemy import tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.base import BaseRepository, PrimaryKeyType
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateHooks,
    BaseDeleteHooks,
    BaseGetHooks,
    BaseGetMultiHooks,
    BaseUpdateHooks,
)


class NestedResourceContextKwargs(BaseContextKwargs):
    """Hierarchical context kwargs."""

    parent_id: Required[PrimaryKeyType]


class NestedResourceHooksMixin[ModelType: Any, TNestedResourceContextKwargs: NestedResourceContextKwargs](
    BaseCreateHooks[ModelType, TNestedResourceContextKwargs],
    BaseUpdateHooks[ModelType, TNestedResourceContextKwargs],
    BaseGetHooks[ModelType, TNestedResourceContextKwargs],
    BaseGetMultiHooks[ModelType, TNestedResourceContextKwargs],
    BaseDeleteHooks[TNestedResourceContextKwargs],
):
    @property
    @abstractmethod
    def parent_repo(self) -> BaseRepository:
        """The repository of the parent resource."""
        pass

    @property
    def fk_name(self) -> str | Sequence[str]:
        """
        The name of the foreign key field(s) in the child model that references the parent.
        Returns a string for a single foreign key, or a sequence of strings for composite foreign keys.
        """
        return "parent_id"

    # ============================================================
    # Helpers
    # ============================================================

    def _get_parent_pk_from_obj(self, obj: ModelType) -> tuple[str, ...]:
        """
        Extracts the parent's PK value(s) from the child object and
        returns them as a normalized string tuple for safe comparison.
        """
        if isinstance(self.fk_name, str):
            extracted_vals = getattr(obj, self.fk_name)
        else:
            extracted_vals = [getattr(obj, fk) for fk in self.fk_name]

        return self.parent_repo.normalize_pk_as_str(extracted_vals)

    async def _check_parent_exists(self, session: AsyncSession, parent_id: PrimaryKeyType) -> None:
        """Check if parent exists, raise NotFoundException if not."""
        if not await self.parent_repo.get_by_pk(session, parent_id):
            raise NotFoundException(log_message=f"Parent {self.parent_repo.model_repr(parent_id)} not found.")

    async def _ensure_ownership(self, session: AsyncSession, obj_pk: PrimaryKeyType, parent_id: PrimaryKeyType):
        """
        Ensure the object belongs to the specific parent.
        This prevents accessing/modifying a child object through a wrong parent URL.
        """
        obj = await self.repo.get_by_pk(session, obj_pk)
        if not obj:
            return

        # Normalize both keys as string tuples to avoid type mismatches (e.g., UUID vs str)
        obj_parent_pk_normalized = self._get_parent_pk_from_obj(obj)
        parent_id_normalized = self.parent_repo.normalize_pk_as_str(parent_id)

        if obj_parent_pk_normalized != parent_id_normalized:
            raise NotFoundException(
                log_message=f"{self.repo.model_repr(obj_pk)} does not belong to {self.parent_repo.model_repr(parent_id)}"
            )

    # ============================================================
    # Create Hooks
    # ============================================================

    @asynccontextmanager
    async def _context_create(self, session: AsyncSession, obj_data: BaseModel, context: TNestedResourceContextKwargs):
        async with super()._context_create(session, obj_data, context):
            parent_id = context["parent_id"]
            await self._check_parent_exists(session, parent_id)
            yield

    @asynccontextmanager
    async def _context_create_multi(
        self, session: AsyncSession, obj_data_list: Sequence[BaseModel], context: TNestedResourceContextKwargs
    ):
        """
        Check parent existence before delegating to the chained Mixins.
        """
        parent_id = context["parent_id"]
        await self._check_parent_exists(session, parent_id)
        async with super()._context_create_multi(session, obj_data_list, context):
            yield

    def _prepare_create_fields(
        self, obj_data: BaseModel, context: TNestedResourceContextKwargs, **update_fields: Any
    ) -> dict[str, Any]:
        """Inject parent_id(s) into the creation data."""
        data = super()._prepare_create_fields(obj_data, context, **update_fields)
        parent_id = context["parent_id"]

        if isinstance(self.fk_name, str):
            data[self.fk_name] = parent_id
        else:
            # Map composite parent keys to their corresponding foreign key fields
            normalized_parent_id = self.parent_repo.normalize_pk(parent_id)
            for fk, p_id_val in zip(self.fk_name, normalized_parent_id, strict=False):
                data[fk] = p_id_val

        return data

    # ============================================================
    # Get Multi (List) Hooks
    # ============================================================

    def _prepare_get_multi_filters(self, context: TNestedResourceContextKwargs) -> list[Any]:
        """Automatically filter by parent_id(s)."""
        filters = super()._prepare_get_multi_filters(context)
        parent_id = context["parent_id"]

        if isinstance(self.fk_name, str):
            filters.append(getattr(self.repo.model, self.fk_name) == parent_id)
        else:
            # Create AND conditions for each part of a composite foreign key
            normalized_parent_id = self.parent_repo.normalize_pk(parent_id)
            for fk, p_id_val in zip(self.fk_name, normalized_parent_id, strict=False):
                filters.append(getattr(self.repo.model, fk) == p_id_val)

        return filters

    @asynccontextmanager
    async def _context_get_multi(self, session: AsyncSession, context: TNestedResourceContextKwargs):
        """Optionally check if parent exists before listing children."""
        async with super()._context_get_multi(session, context):
            # Fail fast if parent doesn't exist, even if list would just be empty.
            await self._check_parent_exists(session, context["parent_id"])
            yield

    # ============================================================
    # Get (Single) Hooks
    # ============================================================

    @asynccontextmanager
    async def _context_get(self, session: AsyncSession, obj_pk: PrimaryKeyType, context: TNestedResourceContextKwargs):
        """Ensure the requested object belongs to the parent context."""
        async with super()._context_get(session, obj_pk, context):
            await self._ensure_ownership(session, obj_pk, context["parent_id"])
            yield

    # ============================================================
    # Update Hooks
    # ============================================================

    @asynccontextmanager
    async def _context_update(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: BaseModel,
        context: TNestedResourceContextKwargs,
        partial: bool = True,
    ):
        """Ensure the object being updated belongs to the parent context."""
        async with super()._context_update(session, obj_pk, obj_data, context, partial=partial):
            await self._ensure_ownership(session, obj_pk, context["parent_id"])
            yield

    # ============================================================
    # Delete Hooks
    # ============================================================

    @asynccontextmanager
    async def _context_delete(
        self, session: AsyncSession, obj_pk: PrimaryKeyType, context: TNestedResourceContextKwargs
    ):
        """Ensure the object being deleted belongs to the parent context."""
        async with super()._context_delete(session, obj_pk, context):
            await self._ensure_ownership(session, obj_pk, context["parent_id"])
            yield

    @asynccontextmanager
    async def _context_delete_multi(
        self, session: AsyncSession, obj_pks: Sequence[PrimaryKeyType], context: TNestedResourceContextKwargs
    ):
        """Bulk ownership check using a single IN query supporting both single and composite keys."""
        async with super()._context_delete_multi(session, obj_pks, context):
            if obj_pks:
                parent_id = context["parent_id"]
                pk_cols = self.repo.primary_keys

                # Handle IN clause for single vs composite primary keys
                if len(pk_cols) == 1:
                    val_list = [self.repo.normalize_pk(pk)[0] for pk in obj_pks]
                    where_clause = pk_cols[0].in_(val_list)
                else:
                    val_list = [self.repo.normalize_pk(pk) for pk in obj_pks]
                    where_clause = tuple_(*pk_cols).in_(val_list)

                objs = await self.repo.get_all(session, where=[where_clause])
                parent_id_normalized = self.parent_repo.normalize_pk_as_str(parent_id)

                for obj in objs:
                    obj_parent_pk_normalized = self._get_parent_pk_from_obj(obj)
                    if obj_parent_pk_normalized != parent_id_normalized:
                        # Extract the actual PK from the object for the error message
                        if len(pk_cols) == 1:
                            err_pk = getattr(obj, pk_cols[0].key)
                        else:
                            err_pk = tuple(getattr(obj, col.key) for col in pk_cols)

                        raise NotFoundException(
                            log_message=f"{self.repo.model_repr(err_pk)} does not belong to "
                            f"{self.parent_repo.model_repr(parent_id)}"
                        )
            yield
