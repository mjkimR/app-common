import abc
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import ColumnElement

from app_layer_base.base.exceptions.basic import BadRequestException
from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateHooks,
    BaseUpdateHooks,
)


class UniqueConstraintHooksMixin[ModelType: Any, TContextKwargs: BaseContextKwargs](
    BaseCreateHooks[ModelType, TContextKwargs], BaseUpdateHooks[ModelType, TContextKwargs], metaclass=abc.ABCMeta
):
    """
    Async Generator-based Unique Constraint Check Hook.

    This mixin allows services to define unique constraints using a generator pattern.
    It automatically checks for duplicates before Create and Update operations.

    Usage Example:
        class UserService(UniqueConstraintHooks, ...):
            async def _unique_constraints(
                self,
                obj_data: Union[UserCreate, UserUpdate],
                context: TContextKwargs
            ) -> AsyncIterator[Tuple[ColumnElement[bool], str]]:
                if obj_data.email:
                    yield User.email == obj_data.email, "Email already exists."
    """

    @abc.abstractmethod
    async def _unique_constraints(
        self,
        obj_data: BaseModel,
        context: TContextKwargs,
    ) -> AsyncIterator[tuple[ColumnElement[bool], str]]:
        """
        [Override Required] Yields SQLAlchemy conditions to check for uniqueness.

        Args:
            obj_data: The Pydantic schema data (Create or Update).
            context: The context dictionary.

        Yields:
            A tuple containing the (SQLAlchemy Condition, Error Message).
        """
        # This is an async generator abstract method.
        # Subclasses must implement this method and use 'yield'.
        yield  # type: ignore (abstract async generator)

    async def _check_constraint(
        self,
        session: AsyncSession,
        condition: ColumnElement[bool],
        message: str,
        exclude_id: Any = None,
    ) -> None:
        """Executes the DB query to check if the unique condition is violated."""
        query_condition = and_(condition, self.repo.model.id != exclude_id) if exclude_id is not None else condition

        is_exists = await self.repo.exists(session, query_condition)
        if is_exists:
            raise BadRequestException(message, status_code=409)

    async def _process_constraints(
        self,
        session: AsyncSession,
        constraints: AsyncIterator[tuple[ColumnElement[bool], str]],
        exclude_id: Any = None,
    ) -> None:
        """Iterates over the constraints generator and performs checks."""
        async for item in constraints:
            if isinstance(item, tuple):
                condition, message = item
            else:
                condition = item
                message = "Data already exists."  # Default fallback message

            await self._check_constraint(session, condition, message, exclude_id)

    # ============================================================
    # Hooks Implementation
    # ============================================================

    @asynccontextmanager
    async def _context_create(self, session: AsyncSession, obj_data: BaseModel, context: TContextKwargs):
        """
        Extends the create context to run unique constraint checks.
        """
        async with super()._context_create(session, obj_data, context):
            constraints = self._unique_constraints(obj_data, context)
            await self._process_constraints(session, constraints)
            yield

    @asynccontextmanager
    async def _context_update(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: BaseModel,
        context: TContextKwargs,
        partial: bool = True,
    ):
        """
        Extends the update context to run unique constraint checks, excluding the current object.
        """
        async with super()._context_update(session, obj_pk, obj_data, context, partial=partial):
            constraints = self._unique_constraints(obj_data, context)
            await self._process_constraints(session, constraints, exclude_id=obj_pk)
            yield
