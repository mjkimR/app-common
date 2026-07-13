import abc
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from pydantic import BaseModel
from sqlalchemy import and_, not_
from sqlalchemy.sql.expression import ColumnElement

from app_layer_base.base.exceptions.basic import ConflictException
from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.services.hooks import (
    BaseContextKwargs,
    CreateHook,
    Operation,
    UpdateHook,
)


class UniqueConstraintHook[ModelType: Any, TContextKwargs: BaseContextKwargs](
    CreateHook[ModelType, TContextKwargs],
    UpdateHook[ModelType, TContextKwargs],
    metaclass=abc.ABCMeta,
):
    """
    Checks for duplicates before create and update.

    Subclass and implement ``constraints`` to declare what must be unique:

        class UserUniqueHook(UniqueConstraintHook[User, BaseContextKwargs]):
            async def constraints(self, op, data):
                if data.email:
                    yield User.email == data.email, "Email already exists."

        class UserService(BaseCreateServiceMixin, ...):
            hooks = (UserUniqueHook(),)
    """

    @abc.abstractmethod
    async def constraints(
        self,
        op: Operation[TContextKwargs],
        data: BaseModel,
    ) -> AsyncIterator[tuple[ColumnElement[bool], str]]:
        """
        [Override Required] Yields (SQLAlchemy condition, error message) pairs.

        A row matching any yielded condition makes the operation a duplicate.
        """
        # This is an async generator abstract method.
        # Subclasses must implement this method and use 'yield'.
        yield  # type: ignore[misc]

    def _is_not(self, op: Operation[TContextKwargs], pk: PrimaryKeyType) -> ColumnElement[bool]:
        """'Any row but this one' -- built from the model's real primary key, single or composite."""
        pk_cols = op.repo.primary_keys
        pk_values = op.repo.normalize_pk(pk)
        return not_(and_(*[col == value for col, value in zip(pk_cols, pk_values, strict=True)]))

    async def _check(
        self,
        op: Operation[TContextKwargs],
        data: BaseModel,
        exclude_pk: PrimaryKeyType | None = None,
    ) -> None:
        async for item in self.constraints(op, data):
            if isinstance(item, tuple):
                condition, message = item
            else:
                condition = item
                message = "Data already exists."  # Default fallback message

            if exclude_pk is not None:
                condition = and_(condition, self._is_not(op, exclude_pk))
            if await op.repo.exists(op.session, condition):
                raise ConflictException(message)

    # ============================================================
    # Hooks
    # ============================================================

    @asynccontextmanager
    async def create_context(self, op: Operation[TContextKwargs], data: BaseModel) -> AsyncIterator[None]:
        await self._check(op, data)
        yield

    @asynccontextmanager
    async def update_context(
        self,
        op: Operation[TContextKwargs],
        pk: PrimaryKeyType,
        data: BaseModel,
        partial: bool = True,
    ) -> AsyncIterator[None]:
        await self._check(op, data, exclude_pk=pk)
        yield
