from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager

from pydantic import BaseModel
from sqlalchemy import tuple_

from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.services.hooks import (
    BaseContextKwargs,
    DeleteHook,
    Operation,
    UpdateHook,
)


class ExistsCheckHook[TContextKwargs: BaseContextKwargs](
    UpdateHook[object, TContextKwargs],
    DeleteHook[TContextKwargs],
):
    """
    Raises NotFoundException when the target row does not exist.

    Stateless and dependency-free; a single instance can be shared:

        class ItemService(BaseDeleteServiceMixin, ...):
            hooks = (ExistsCheckHook(),)
    """

    @asynccontextmanager
    async def update_context(
        self,
        op: Operation[TContextKwargs],
        pk: PrimaryKeyType,
        data: BaseModel,
        partial: bool = True,
    ) -> AsyncGenerator[None]:
        if not await op.repo.get_by_pk(op.session, pk):
            raise NotFoundException(log_message=f"{op.repo.model_repr(pk)} does not exist.")
        yield

    @asynccontextmanager
    async def delete_context(self, op: Operation[TContextKwargs], pk: PrimaryKeyType) -> AsyncGenerator[None]:
        if not await op.repo.get_by_pk(op.session, pk):
            raise NotFoundException(log_message=f"{op.repo.model_repr(pk)} does not exist.")
        yield

    @asynccontextmanager
    async def delete_context_multi(
        self, op: Operation[TContextKwargs], pks: Sequence[PrimaryKeyType]
    ) -> AsyncGenerator[None]:
        """Replaces this hook's per-item check with a single IN query."""
        if pks:
            pk_cols = op.repo.primary_keys

            if len(pk_cols) == 1:
                val_list = [op.repo.normalize_pk(pk)[0] for pk in pks]
                where_clause = pk_cols[0].in_(val_list)
            else:
                val_list = [op.repo.normalize_pk(pk) for pk in pks]
                where_clause = tuple_(*pk_cols).in_(val_list)

            existing_objs = await op.repo.get_all(op.session, where=[where_clause])

            # Normalize to string tuples so UUID vs str never causes a false miss.
            existing = set()
            for obj in existing_objs:
                if len(pk_cols) == 1:
                    obj_pk = getattr(obj, pk_cols[0].key)
                else:
                    obj_pk = tuple(getattr(obj, col.key) for col in pk_cols)
                existing.add(op.repo.normalize_pk_as_str(obj_pk))

            missing = [pk for pk in pks if op.repo.normalize_pk_as_str(pk) not in existing]
            if missing:
                missing_reprs = ", ".join(op.repo.model_repr(pk) for pk in missing)
                raise NotFoundException(log_message=f"The following objects do not exist: {missing_reprs}")
        yield
