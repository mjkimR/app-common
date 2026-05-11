import abc
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Tuple, Union

from pydantic import BaseModel

from app_base.adapter.nosql_db.hooks.base import (
    BaseNoSQLCreateHooks,
    BaseNoSQLUpdateHooks,
    CreateSchemaType,
    TContextKwargs,
    UpdateSchemaType,
)
from app_base.adapter.nosql_db.interface import NoSQLDBProvider
from app_base.base.exceptions.basic import BadRequestException


class NoSQLUniqueConstraintHooksMixin(BaseNoSQLCreateHooks, BaseNoSQLUpdateHooks, metaclass=abc.ABCMeta):
    """
    Async Generator-based Unique Constraint Check Hook for NoSQL.
    """

    @abc.abstractmethod
    async def _unique_constraints(
        self,
        obj_data: Union[CreateSchemaType, UpdateSchemaType],
        context: TContextKwargs,
    ) -> AsyncIterator[Tuple[list[tuple[str, str, Any]], str]]:
        """
        [Override Required] Yields NoSQL filter conditions to check for uniqueness.

        Yields:
            A tuple containing (filters, Error Message).
            filters: list of (field, op, value) tuples.
        """
        yield  # type: ignore

    async def _check_constraint(
        self,
        provider: NoSQLDBProvider,
        filters: list[tuple[str, str, Any]],
        message: str,
        exclude_id: str | None = None,
    ) -> None:
        """Executes the NoSQL query to check if the unique condition is violated."""
        results = await self.repo.get_multi(provider, filters=filters, limit=2)

        for item in results.items:
            item_id = str(getattr(item, "id", ""))
            if exclude_id is None or item_id != exclude_id:
                raise BadRequestException(message, status_code=409)

    async def _process_constraints(
        self,
        provider: NoSQLDBProvider,
        constraints: AsyncIterator[Tuple[list[tuple[str, str, Any]], str]],
        exclude_id: str | None = None,
    ) -> None:
        """Iterates over the constraints generator and performs checks."""
        async for item in constraints:
            if isinstance(item, tuple):
                filters, message = item
            else:
                filters = item
                message = "Data already exists."

            await self._check_constraint(provider, filters, message, exclude_id)

    @asynccontextmanager
    async def _context_create(
        self, provider: NoSQLDBProvider, document_id: str, obj_data: BaseModel, context: TContextKwargs
    ):
        async with super()._context_create(provider, document_id, obj_data, context):
            constraints = self._unique_constraints(obj_data, context)
            await self._process_constraints(provider, constraints)
            yield

    @asynccontextmanager
    async def _context_update(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        obj_data: BaseModel,
        context: TContextKwargs,
        partial: bool = True,
    ):
        async with super()._context_update(provider, document_id, obj_data, context, partial):
            constraints = self._unique_constraints(obj_data, context)
            await self._process_constraints(provider, constraints, exclude_id=document_id)
            yield
