import abc
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Tuple, Union

from pydantic import BaseModel
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import ColumnElement

from app_base.base.exceptions.basic import BadRequestException
from app_base.base.services.base import (
    BaseCreateHooks,
    BaseUpdateHooks,
    CreateSchemaType,
    TContextKwargs,
    UpdateSchemaType,
)


class UniqueConstraintHooksMixin(BaseCreateHooks, BaseUpdateHooks, metaclass=abc.ABCMeta):
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
        obj_data: Union[CreateSchemaType, UpdateSchemaType],
        context: TContextKwargs,
    ) -> AsyncIterator[Tuple[ColumnElement[bool], str]]:
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
        if exclude_id is not None:
            # For updates: Check if record exists matching the condition BUT has a different ID.
            query_condition = and_(condition, self.repo.model.id != exclude_id)
        else:
            # For creates: Just check if the condition matches any record.
            query_condition = condition

        is_exists = await self.repo.exists(session, query_condition)
        if is_exists:
            raise BadRequestException(message)

    async def _process_constraints(
        self,
        session: AsyncSession,
        constraints: AsyncIterator[Tuple[ColumnElement[bool], str]],
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
        obj_id: uuid.UUID,
        obj_data: BaseModel,
        context: TContextKwargs,
    ):
        """
        Extends the update context to run unique constraint checks, excluding the current object.
        """
        async with super()._context_update(session, obj_id, obj_data, context):
            constraints = self._unique_constraints(obj_data, context)
            await self._process_constraints(session, constraints, exclude_id=obj_id)
            yield
