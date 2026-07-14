from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import Any, Required

from pydantic import BaseModel
from sqlalchemy import tuple_

from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.base import BaseRepository, PrimaryKeyType
from app_layer_base.base.services.hooks import (
    BaseContextKwargs,
    CreateHook,
    DeleteHook,
    GetHook,
    GetMultiHook,
    Operation,
    UpdateHook,
)


class NestedResourceContextKwargs(BaseContextKwargs):
    """Hierarchical context kwargs."""

    parent_id: Required[PrimaryKeyType]


class NestedResourceHook[ModelType: Any, TNestedResourceContextKwargs: NestedResourceContextKwargs](
    CreateHook[ModelType, TNestedResourceContextKwargs],
    UpdateHook[ModelType, TNestedResourceContextKwargs],
    GetHook[ModelType, TNestedResourceContextKwargs],
    GetMultiHook[ModelType, TNestedResourceContextKwargs],
    DeleteHook[TNestedResourceContextKwargs],
):
    """
    Scopes every operation to ``context["parent_id"]``.

    Creates get the foreign key injected; reads, updates and deletes are refused
    when the row belongs to a different parent; lists are filtered by parent.

        class ChapterService(BaseCreateServiceMixin, ...):
            @cached_property
            def hooks(self):
                return (NestedResourceHook(self.book_repo, fk_name="book_id"),)
    """

    required_context_keys = frozenset({"parent_id"})

    def __init__(self, parent_repo: BaseRepository, fk_name: str | Sequence[str] = "parent_id"):
        """
        Args:
            parent_repo: repository of the parent resource.
            fk_name: foreign key field(s) on the child model pointing at the parent.
                A string for a single key, a sequence for a composite key.
        """
        self.parent_repo = parent_repo
        self.fk_name = fk_name

    # ============================================================
    # Helpers
    # ============================================================

    def _parent_pk_of(self, obj: ModelType) -> tuple[str, ...]:
        """The object's parent pk, normalized to a string tuple for safe comparison."""
        if isinstance(self.fk_name, str):
            extracted = getattr(obj, self.fk_name)
        else:
            extracted = [getattr(obj, fk) for fk in self.fk_name]
        return self.parent_repo.normalize_pk_as_str(extracted)

    async def _check_parent_exists(
        self, op: Operation[TNestedResourceContextKwargs], parent_id: PrimaryKeyType
    ) -> None:
        if not await self.parent_repo.get_by_pk(op.session, parent_id):
            raise NotFoundException(log_message=f"Parent {self.parent_repo.model_repr(parent_id)} not found.")

    async def _ensure_ownership(self, op: Operation[TNestedResourceContextKwargs], pk: PrimaryKeyType) -> None:
        """
        Refuse to touch a child through the wrong parent.

        A missing row is left alone -- that is ExistsCheckHook's call to make.
        """
        obj = await op.repo.get_by_pk(op.session, pk)
        if not obj:
            return

        parent_id = op.context["parent_id"]
        if self._parent_pk_of(obj) != self.parent_repo.normalize_pk_as_str(parent_id):
            raise NotFoundException(
                log_message=f"{op.repo.model_repr(pk)} does not belong to {self.parent_repo.model_repr(parent_id)}"
            )

    # ============================================================
    # Create
    # ============================================================

    @asynccontextmanager
    async def create_context(
        self, op: Operation[TNestedResourceContextKwargs], data: BaseModel
    ) -> AsyncGenerator[None]:
        await self._check_parent_exists(op, op.context["parent_id"])
        yield

    @asynccontextmanager
    async def create_context_multi(
        self, op: Operation[TNestedResourceContextKwargs], data_list: Sequence[BaseModel]
    ) -> AsyncGenerator[None]:
        """Replaces this hook's per-item parent lookup with a single one."""
        await self._check_parent_exists(op, op.context["parent_id"])
        yield

    def create_prepare_fields(
        self,
        op: Operation[TNestedResourceContextKwargs],
        data: BaseModel,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        """Inject the parent key(s) into the row being created."""
        fields = dict(fields)
        parent_id = op.context["parent_id"]

        if isinstance(self.fk_name, str):
            fields[self.fk_name] = parent_id
        else:
            normalized = self.parent_repo.normalize_pk(parent_id)
            for fk, value in zip(self.fk_name, normalized, strict=False):
                fields[fk] = value

        return fields

    # ============================================================
    # Get multi (list)
    # ============================================================

    def get_multi_prepare_filters(self, op: Operation[TNestedResourceContextKwargs]) -> list[Any]:
        """Filter the list down to this parent's children."""
        filters: list[Any] = []
        parent_id = op.context["parent_id"]

        if isinstance(self.fk_name, str):
            filters.append(getattr(op.repo.model, self.fk_name) == parent_id)
        else:
            normalized = self.parent_repo.normalize_pk(parent_id)
            for fk, value in zip(self.fk_name, normalized, strict=False):
                filters.append(getattr(op.repo.model, fk) == value)

        return filters

    @asynccontextmanager
    async def get_multi_context(self, op: Operation[TNestedResourceContextKwargs]) -> AsyncGenerator[None]:
        # Fail fast if the parent doesn't exist, rather than returning an empty list.
        await self._check_parent_exists(op, op.context["parent_id"])
        yield

    # ============================================================
    # Get / Update / Delete -- ownership
    # ============================================================

    @asynccontextmanager
    async def get_context(
        self, op: Operation[TNestedResourceContextKwargs], pk: PrimaryKeyType
    ) -> AsyncGenerator[None]:
        await self._ensure_ownership(op, pk)
        yield

    @asynccontextmanager
    async def update_context(
        self,
        op: Operation[TNestedResourceContextKwargs],
        pk: PrimaryKeyType,
        data: BaseModel,
        partial: bool = True,
    ) -> AsyncGenerator[None]:
        await self._ensure_ownership(op, pk)
        yield

    @asynccontextmanager
    async def delete_context(
        self, op: Operation[TNestedResourceContextKwargs], pk: PrimaryKeyType
    ) -> AsyncGenerator[None]:
        await self._ensure_ownership(op, pk)
        yield

    @asynccontextmanager
    async def delete_context_multi(
        self, op: Operation[TNestedResourceContextKwargs], pks: Sequence[PrimaryKeyType]
    ) -> AsyncGenerator[None]:
        """Replaces this hook's per-item ownership lookup with a single IN query."""
        if pks:
            parent_id = op.context["parent_id"]
            pk_cols = op.repo.primary_keys

            if len(pk_cols) == 1:
                val_list = [op.repo.normalize_pk(pk)[0] for pk in pks]
                where_clause = pk_cols[0].in_(val_list)
            else:
                val_list = [op.repo.normalize_pk(pk) for pk in pks]
                where_clause = tuple_(*pk_cols).in_(val_list)

            objs = await op.repo.get_all(op.session, where=[where_clause])
            parent_id_normalized = self.parent_repo.normalize_pk_as_str(parent_id)

            for obj in objs:
                if self._parent_pk_of(obj) != parent_id_normalized:
                    if len(pk_cols) == 1:
                        err_pk = getattr(obj, pk_cols[0].key)
                    else:
                        err_pk = tuple(getattr(obj, col.key) for col in pk_cols)

                    raise NotFoundException(
                        log_message=f"{op.repo.model_repr(err_pk)} does not belong to "
                        f"{self.parent_repo.model_repr(parent_id)}"
                    )
        yield
