from collections.abc import Sequence
from contextlib import asynccontextmanager
from typing import Any

from pydantic import BaseModel
from sqlalchemy import tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app_base.base.exceptions.basic import NotFoundException
from app_base.base.repos.base import PrimaryKeyType
from app_base.base.services.base import BaseContextKwargs, BaseDeleteHooks, BaseUpdateHooks


class ExistsCheckHooksMixin[ModelType: Any, TContextKwargs: BaseContextKwargs](
    BaseUpdateHooks[ModelType, TContextKwargs], BaseDeleteHooks[TContextKwargs]
):
    @asynccontextmanager
    async def _context_update(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: BaseModel,
        context: TContextKwargs,
        partial: bool = True,
    ):
        # Ensure the super() call is included to guarantee hook chaining
        async with super()._context_update(session, obj_pk, obj_data, context, partial=partial):
            if not await self.repo.get_by_pk(session, obj_pk):
                raise NotFoundException(log_message=f"{self.repo.model_repr(obj_pk)} does not exist.")
            yield

    @asynccontextmanager
    async def _context_delete(self, session: AsyncSession, obj_pk: PrimaryKeyType, context: TContextKwargs):
        async with super()._context_delete(session, obj_pk, context):
            if not await self.repo.get_by_pk(session, obj_pk):
                raise NotFoundException(log_message=f"{self.repo.model_repr(obj_pk)} does not exist.")
            yield

    @asynccontextmanager
    async def _context_delete_multi(
        self, session: AsyncSession, obj_pks: Sequence[PrimaryKeyType], context: TContextKwargs
    ):
        """Bulk existence check using a single IN query supporting both single and composite keys."""
        async with super()._context_delete_multi(session, obj_pks, context):
            if obj_pks:
                pk_cols = self.repo.primary_keys

                # 1. Create an IN query condition depending on whether the primary key is single or composite
                if len(pk_cols) == 1:
                    val_list = [self.repo.normalize_pk(pk)[0] for pk in obj_pks]
                    where_clause = pk_cols[0].in_(val_list)
                else:
                    val_list = [self.repo.normalize_pk(pk) for pk in obj_pks]
                    where_clause = tuple_(*pk_cols).in_(val_list)

                # 2. Bulk query to fetch existing objects
                existing_objs = await self.repo.get_all(session, where=[where_clause])

                # 3. Build a set of normalized string tuples from the retrieved PKs to prevent type mismatches (e.g., UUID vs str)
                existing_set = set()
                for obj in existing_objs:
                    if len(pk_cols) == 1:
                        obj_pk = getattr(obj, pk_cols[0].key)
                    else:
                        obj_pk = tuple(getattr(obj, col.key) for col in pk_cols)
                    existing_set.add(self.repo.normalize_pk_as_str(obj_pk))

                # 4. Filter out the requested PKs that do not exist (i.e., not found in the set)
                missing = [pk for pk in obj_pks if self.repo.normalize_pk_as_str(pk) not in existing_set]

                # 5. Raise an exception if any requested objects are missing
                if missing:
                    missing_reprs = ", ".join(self.repo.model_repr(pk) for pk in missing)
                    raise NotFoundException(log_message=f"The following objects do not exist: {missing_reprs}")
            yield
