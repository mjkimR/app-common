import uuid
from datetime import datetime, timezone
from typing import Any, Generic, Optional, Sequence, TypeVar, Union, cast

from pydantic import BaseModel
from sqlalchemy import (
    Column,
    CursorResult,
    and_,
    delete,
    func,
    literal,
    or_,
    select,
    update,
)
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.base import ExecutableOption
from sqlalchemy.sql.elements import ColumnElement, UnaryExpression
from sqlalchemy.sql.selectable import Select

from app_base.base.schemas.paginated import PaginatedList
from app_base.core.log import logger
from app_base.utils.type_hint import SeqOrOneOrNone, to_sequence

ModelType = TypeVar("ModelType", bound=Any)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
PutSchemaType = TypeVar("PutSchemaType", bound=BaseModel)
PatchSchemaType = TypeVar("PatchSchemaType", bound=BaseModel)

PrimaryKeyType = Union[Sequence[Union[str, int, uuid.UUID]], Union[str, int, uuid.UUID]]
WhereClause = SeqOrOneOrNone[ColumnElement[bool]]


class BaseRepository(
    Generic[
        ModelType,
        CreateSchemaType,
        PutSchemaType,
        PatchSchemaType,
    ]
):
    BATCH_SIZE = 1000

    model: type[ModelType]
    resource_name: str

    default_order_by_col: Optional[str] = "created_at"
    is_deleted_column: Optional[str] = "is_deleted"
    deleted_at_column: Optional[str] = "deleted_at"

    def __init__(self):
        inspector = sa_inspect(self.model)
        if inspector is None:  # pragma: no cover
            raise ValueError("Model inspection failed, resulting in None.")
        self._primary_keys: Sequence[Column] = inspector.mapper.primary_key
        self._model_columns: set[str] = {col.key for col in inspector.mapper.columns}

    @classmethod
    def model_name(cls):
        return cls.model.__name__

    @property
    def primary_keys(self) -> Sequence[Column]:
        """The primary key columns of the model."""
        return self._primary_keys

    # ============================================================
    # PK Helpers
    # ============================================================

    def normalize_pk(self, pk: PrimaryKeyType) -> tuple[Any, ...]:
        """Normalize single or composite primary key(s) into a consistent tuple format."""
        if not isinstance(pk, Sequence) or isinstance(pk, str):
            return (pk,)
        return tuple(pk)

    def normalize_pk_as_str(self, pk: PrimaryKeyType) -> tuple[str, ...]:
        """Normalize primary key(s) into a tuple of strings for safe value comparisons (e.g., UUID vs str)."""
        return tuple(str(x) for x in self.normalize_pk(pk))

    # ============================================================

    def model_repr(self, pk: PrimaryKeyType):
        if not self._primary_keys:
            raise ValueError("No primary key defined for this model.")

        pk_values = self.normalize_pk(pk)

        if len(self._primary_keys) != len(pk_values):
            raise ValueError(
                f"Incorrect number of primary key values provided. Expected {len(self._primary_keys)}, got {len(pk_values)}."
            )
        pk_str = ", ".join(
            f"{pk_col.key}={str(value)}" for pk_col, value in zip(self._primary_keys, pk_values, strict=False)
        )
        return f"{self.model_name()}({pk_str})"

    def _get_primary_key_filters(self, pk: PrimaryKeyType):
        if not self._primary_keys:
            raise ValueError("No primary key defined for this model.")

        pk_values = self.normalize_pk(pk)

        if len(self._primary_keys) != len(pk_values):
            raise ValueError(
                f"Incorrect number of primary key values provided. Expected {len(self._primary_keys)}, got {len(pk_values)}."
            )

        return [pk_col == value for pk_col, value in zip(self._primary_keys, pk_values, strict=False)]

    def _select(self, where: WhereClause = (), order_by: SeqOrOneOrNone[UnaryExpression] = ()) -> Select:
        stmt = select(self.model)
        if where is not None:
            where = to_sequence(where)
            stmt = stmt.where(*where)

        if order_by is not None:
            order_by = to_sequence(order_by)
            stmt = stmt.order_by(*order_by)
        else:
            if self.default_order_by_col:
                if hasattr(self.model, self.default_order_by_col):
                    default_order_by = getattr(self.model, self.default_order_by_col)
                    if default_order_by is not None:
                        stmt = stmt.order_by(default_order_by.desc())
                else:
                    logger.warning(
                        f"Default order by column '{self.default_order_by_col}' does not exist in model {self.model.__name__}. Skipping default ordering. "
                        f"Please check the configuration of 'default_order_by_col' at {self.__class__.__name__} or ensure that the column exists in the model."
                    )
        return stmt

    async def get(
        self,
        session: AsyncSession,
        where: WhereClause = (),
        order_by: SeqOrOneOrNone[UnaryExpression] = (),
    ) -> Optional[ModelType]:
        stmt = self._select(where, order_by)
        stmt = stmt.limit(1)

        db_row = await session.execute(stmt)
        return db_row.scalar_one_or_none()

    async def get_by_pk(self, session: AsyncSession, pk: PrimaryKeyType) -> Optional[ModelType]:
        if not self._primary_keys:
            raise ValueError("No primary key defined for this model.")

        pk_values = self.normalize_pk(pk)

        if len(self._primary_keys) != len(pk_values):
            raise ValueError(
                f"Incorrect number of primary key values provided. Expected {len(self._primary_keys)}, got {len(pk_values)}."
            )

        if len(self._primary_keys) == 1:
            ident = pk_values[0]
        else:
            ident = dict(zip([pk_col.key for pk_col in self._primary_keys], pk_values, strict=False))

        return await session.get(self.model, ident)

    async def exists(
        self,
        session: AsyncSession,
        where: WhereClause = (),
    ) -> bool:
        stmt = select(literal(1))  # select 1
        stmt = stmt.select_from(self.model)
        if where is not None:
            where = to_sequence(where)
            stmt = stmt.where(*where)
        stmt = stmt.limit(1)

        result = await session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        session: AsyncSession,
        obj_in: CreateSchemaType,
        **update_fields: Any,
    ) -> ModelType:
        obj_dict = obj_in.model_dump()
        obj_dict = {k: v for k, v in obj_dict.items() if k in self._model_columns}  # Filter out non-model fields
        obj_dict.update(update_fields)
        db_obj: ModelType = self.model(**obj_dict)
        session.add(db_obj)
        await session.flush()
        await session.refresh(db_obj)
        return db_obj

    async def create_multi(
        self,
        session: AsyncSession,
        objs_in: Sequence[CreateSchemaType],
        extra_fields_list: Optional[Sequence[dict[str, Any]]] = None,
        **update_fields: Any,
    ) -> Sequence[ModelType]:
        if extra_fields_list is not None and len(extra_fields_list) != len(objs_in):
            raise ValueError(
                f"extra_fields_list length ({len(extra_fields_list)}) must match objs_in length ({len(objs_in)})."
            )
        db_objs = []
        for idx, obj_in in enumerate(objs_in):
            obj_dict = obj_in.model_dump()
            obj_dict = {k: v for k, v in obj_dict.items() if k in self._model_columns}  # Filter out non-model fields
            obj_dict.update(update_fields)
            if extra_fields_list is not None:
                obj_dict.update(extra_fields_list[idx])
            db_objs.append(self.model(**obj_dict))

        created_objs: list[ModelType] = []
        for i in range(0, len(db_objs), self.BATCH_SIZE):
            chunk = db_objs[i : i + self.BATCH_SIZE]
            session.add_all(chunk)
            await session.flush()
            # ⚡ Bolt Optimization: Removed loop calling `await session.refresh(obj)` here.
            # `session.flush()` already assigns primary keys and server defaults.
            # Calling `refresh` sequentially for each obj results in an N+1 queries
            # bottleneck for bulk creation, slowing down inserts significantly.
            created_objs.extend(chunk)

        return created_objs

    async def get_multi(
        self,
        session: AsyncSession,
        offset: int = 0,
        limit: Optional[int] = 100,
        where: WhereClause = (),
        order_by: SeqOrOneOrNone[UnaryExpression] = (),
        select_options: SeqOrOneOrNone[ExecutableOption] = (),
    ) -> PaginatedList[ModelType]:
        if limit is not None and limit < 0:
            raise ValueError("Limit must be non-negative.")
        if offset < 0:
            raise ValueError("Offset must be non-negative.")

        # Total count
        count_stmt = select(func.count()).select_from(self.model)
        if where is not None:
            where = to_sequence(where)
            count_stmt = count_stmt.where(*where)
        total_count_result = await session.execute(count_stmt)
        total_count = total_count_result.scalar_one()

        # Query
        stmt = self._select(where=where, order_by=order_by)
        stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        if select_options:
            select_options = to_sequence(select_options)
            stmt = stmt.options(*select_options)

        result = await session.execute(stmt)
        data = result.scalars().all()

        return PaginatedList(
            items=data,
            total_count=total_count,
            offset=offset,
            limit=limit,
        )

    async def get_all(
        self,
        session: AsyncSession,
        where: WhereClause = (),
        order_by: SeqOrOneOrNone[UnaryExpression] = (),
    ) -> Sequence[ModelType]:
        res = await self.get_multi(
            session,
            offset=0,
            limit=None,
            where=where,
            order_by=order_by,
        )
        return res.items

    async def update_by_pk(
        self,
        session: AsyncSession,
        pk: PrimaryKeyType,
        obj_in: Union[PutSchemaType, PatchSchemaType, dict[str, Any]],
        return_updated_obj: bool = True,
        partial: bool = True,
        **update_fields: Any,
    ) -> Optional[ModelType]:
        db_obj = await self.get_by_pk(session, pk)
        if not db_obj:
            return None

        if isinstance(obj_in, dict):
            update_data = obj_in.copy()
        else:
            update_data = obj_in.model_dump(exclude_unset=partial)

        update_data = {k: v for k, v in update_data.items() if k in self._model_columns}  # Filter out non-model fields
        update_data.update(update_fields)  # Include additional update fields

        if not update_data and partial:
            raise ValueError("Update data cannot be empty.")

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        session.add(db_obj)
        await session.flush()
        await session.refresh(db_obj)

        return db_obj if return_updated_obj else None

    async def delete_by_pk(
        self,
        session: AsyncSession,
        pk: PrimaryKeyType,
        soft_delete: bool = False,
    ) -> bool:
        filters = self._get_primary_key_filters(pk)
        if soft_delete:
            if not self.is_deleted_column:
                raise ValueError("is_deleted_column is not configured for soft delete.")
            has_is_deleted = hasattr(self.model, self.is_deleted_column)

            if not has_is_deleted:
                raise ValueError(
                    f"Soft delete requires the column '{self.is_deleted_column}' in model {self.model.__name__}."
                )

            if self.deleted_at_column and not hasattr(self.model, self.deleted_at_column):
                raise ValueError(
                    f"Soft delete is configured to use '{self.deleted_at_column}', but it's missing in model {self.model.__name__}."
                )

            update_values: dict[str, Any] = {self.is_deleted_column: True}
            if self.deleted_at_column and hasattr(self.model, self.deleted_at_column):
                update_values[self.deleted_at_column] = datetime.now(timezone.utc)

            stmt = update(self.model).filter(*filters).values(**update_values)
        else:
            stmt = delete(self.model).filter(*filters)

        result = await session.execute(stmt)
        cursor_result = cast(CursorResult, result)
        deleted_or_updated = int(cursor_result.rowcount) > 0
        if deleted_or_updated:
            await session.flush()
        return deleted_or_updated

    async def delete_by_pk_multi(
        self,
        session: AsyncSession,
        pks: Sequence[PrimaryKeyType],
        soft_delete: bool = False,
    ) -> int:
        if not pks:
            return 0

        total_affected_rows = 0

        for i in range(0, len(pks), self.BATCH_SIZE):
            chunk = pks[i : i + self.BATCH_SIZE]

            filter_clauses = []
            for pk in chunk:
                pk_filters = self._get_primary_key_filters(pk)
                filter_clauses.append(and_(*pk_filters))

            where_clause = or_(*filter_clauses)

            if soft_delete:
                if not self.is_deleted_column:
                    raise ValueError("is_deleted_column is not configured for soft delete.")
                has_is_deleted = hasattr(self.model, self.is_deleted_column)
                if not has_is_deleted:
                    raise ValueError(
                        f"Soft delete requires the column '{self.is_deleted_column}' in model {self.model.__name__}."
                    )
                if self.deleted_at_column and not hasattr(self.model, self.deleted_at_column):
                    raise ValueError(
                        f"Soft delete is configured to use '{self.deleted_at_column}', but it's missing in model {self.model.__name__}."
                    )

                update_values: dict[str, Any] = {self.is_deleted_column: True}
                if self.deleted_at_column and hasattr(self.model, self.deleted_at_column):
                    update_values[self.deleted_at_column] = datetime.now(timezone.utc)

                stmt = update(self.model).where(where_clause).values(**update_values)
            else:
                stmt = delete(self.model).where(where_clause)

            result = await session.execute(stmt)
            cursor_result = cast(CursorResult, result)
            total_affected_rows += cursor_result.rowcount or 0

        if total_affected_rows > 0:
            await session.flush()

        return total_affected_rows
