"""
Transaction-wrapping CRUD use cases.

Each ``execute()`` owns exactly one ``AsyncTransaction`` by default. Two rules
follow:

- Never call a use case from inside a use case: the inner ``execute()`` opens a
  second, independent session, which commits separately from -- and can deadlock
  with -- the outer one. Compose at the service layer instead: a composite use
  case opens one transaction and calls several services with that session.
- ``_execute`` / ``_post_execute`` overrides are orchestration seams for one
  scenario, not a home for business rules. An invariant that must hold on every
  write path belongs in a service hook, where every caller gets it.

Escape hatch: ``execute(..., session=existing)`` makes the use case JOIN an
outer transaction instead of owning one, so it can be reused inside another
without the split-session hazard above. It is deliberately not the default:
prefer service-layer composition, and reach for ``session=`` only when reusing a
use case as-is beats refactoring it right now (and the caller owns the commit and
any after-commit dispatch). Note that read use cases with read hooks and write
use cases still run their hooks either way; only the transaction boundary moves.
"""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from app_layer_base.base.repos.base import (
    PrimaryKeyType,
)
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from app_layer_base.base.services.base import (
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from app_layer_base.base.usecases.base import BaseUseCase
from app_layer_base.core.database.transaction import AsyncTransaction


class BaseGetUseCase[
    TBaseGetService: BaseGetServiceMixin,
    ModelType,
    TContextKwargs,
](BaseUseCase):
    def __init__(self, service: TBaseGetService):
        self.service = service

    async def _execute(
        self, session: AsyncSession, obj_pk: PrimaryKeyType, context: TContextKwargs | None
    ) -> ModelType | None:
        return await self.service.get(session, obj_pk, context=context)

    async def execute(
        self,
        obj_pk: PrimaryKeyType,
        context: TContextKwargs | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> ModelType | None:
        async with AsyncTransaction(session=session) as session:
            return await self._execute(session, obj_pk, context=context)


class BaseGetMultiUseCase[
    TBaseGetMultiService: BaseGetMultiServiceMixin,
    ModelType,
    TContextKwargs,
](BaseUseCase):
    def __init__(self, service: TBaseGetMultiService):
        self.service = service

    async def _execute(
        self,
        session: AsyncSession,
        query_options: ListQueryOptions,
        context: TContextKwargs | None = None,
    ) -> PaginatedList[ModelType]:
        return await self.service.get_multi(
            session,
            query_options=query_options,
            context=context,
        )

    async def execute(
        self,
        query_options: ListQueryOptions | None = None,
        context: TContextKwargs | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> PaginatedList[ModelType]:
        query_options = query_options or ListQueryOptions()
        async with AsyncTransaction(session=session) as session:
            return await self._execute(
                session,
                query_options=query_options,
                context=context,
            )


class BaseCreateUseCase[
    TBaseCreateService: BaseCreateServiceMixin,
    ModelType,
    CreateSchemaType,
    TContextKwargs,
](BaseUseCase):
    def __init__(self, service: TBaseCreateService):
        self.service = service

    @asynccontextmanager
    async def _context_execute(
        self,
        session: AsyncSession,
        obj_data: CreateSchemaType,
        context: TContextKwargs | None,
    ):
        yield

    async def _execute(
        self,
        session: AsyncSession,
        obj_data: CreateSchemaType,
        context: TContextKwargs | None,
    ) -> ModelType:
        return await self.service.create(session, obj_data, context=context)

    async def _post_execute(
        self,
        session: AsyncSession,
        obj: ModelType,
        obj_data: CreateSchemaType,
        context: TContextKwargs | None,
    ) -> ModelType:
        return obj

    async def execute(
        self,
        obj_data: CreateSchemaType,
        context: TContextKwargs | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> ModelType:
        async with AsyncTransaction(session=session) as session, self._context_execute(session, obj_data, context):
            obj = await self._execute(session, obj_data, context=context)
            obj = await self._post_execute(session, obj, obj_data, context)
            return obj


class BaseUpdateUseCase[
    TBaseUpdateService: BaseUpdateServiceMixin,
    ModelType,
    PutSchemaType,
    PatchSchemaType,
    TContextKwargs,
](BaseUseCase, ABC):
    def __init__(self, service: TBaseUpdateService):
        self.service = service

    @asynccontextmanager
    async def _context_execute(
        self,
        session: AsyncSession,
        obj_data: PutSchemaType | PatchSchemaType,
        context: TContextKwargs | None,
    ):
        yield

    @abstractmethod
    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: PutSchemaType | PatchSchemaType,
        context: TContextKwargs | None,
    ) -> ModelType | None:
        pass

    async def _post_execute(
        self,
        session: AsyncSession,
        obj: ModelType | None,
        obj_data: PutSchemaType | PatchSchemaType,
        context: TContextKwargs | None,
    ) -> ModelType | None:
        return obj

    async def execute(
        self,
        obj_pk: PrimaryKeyType,
        obj_data: PutSchemaType | PatchSchemaType,
        context: TContextKwargs | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> ModelType | None:
        async with AsyncTransaction(session=session) as session, self._context_execute(session, obj_data, context):
            obj = await self._execute(session, obj_pk, obj_data, context=context)
            obj = await self._post_execute(session, obj, obj_data, context)
            return obj


class BasePatchUseCase[
    TBaseUpdateService: BaseUpdateServiceMixin,
    ModelType,
    PutSchemaType,
    PatchSchemaType,
    TContextKwargs,
](BaseUpdateUseCase[TBaseUpdateService, ModelType, PutSchemaType, PatchSchemaType, TContextKwargs]):
    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: PatchSchemaType,
        context: TContextKwargs | None,
    ) -> ModelType | None:
        return await self.service.patch(session, obj_pk, obj_data, context=context)

    async def execute(
        self,
        obj_pk: PrimaryKeyType,
        obj_data: PatchSchemaType,
        context: TContextKwargs | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> ModelType | None:
        return await super().execute(obj_pk, obj_data, context=context, session=session)


class BasePutUseCase[
    TBaseUpdateService: BaseUpdateServiceMixin,
    ModelType,
    PutSchemaType,
    PatchSchemaType,
    TContextKwargs,
](BaseUpdateUseCase[TBaseUpdateService, ModelType, PutSchemaType, PatchSchemaType, TContextKwargs]):
    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        obj_data: PutSchemaType,
        context: TContextKwargs | None,
    ) -> ModelType | None:
        return await self.service.put(session, obj_pk, obj_data, context=context)

    async def execute(
        self,
        obj_pk: PrimaryKeyType,
        obj_data: PutSchemaType,
        context: TContextKwargs | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> ModelType | None:
        return await super().execute(obj_pk, obj_data, context=context, session=session)


class BaseDeleteUseCase[
    TBaseDeleteService: BaseDeleteServiceMixin,
    ModelType,
    TContextKwargs,
](BaseUseCase):
    def __init__(self, service: TBaseDeleteService):
        self.service = service

    @asynccontextmanager
    async def _context_execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        context: TContextKwargs | None,
    ):
        yield

    async def _execute(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        context: TContextKwargs | None,
    ) -> DeleteResponse:
        return await self.service.delete(session, obj_pk, context=context)

    async def _post_execute(
        self,
        session: AsyncSession,
        obj: DeleteResponse,
        context: TContextKwargs | None,
    ) -> DeleteResponse:
        return obj

    async def execute(
        self,
        obj_pk: PrimaryKeyType,
        context: TContextKwargs | None = None,
        *,
        session: AsyncSession | None = None,
    ):
        async with AsyncTransaction(session=session) as session, self._context_execute(session, obj_pk, context):
            obj = await self._execute(session, obj_pk, context=context)
            return await self._post_execute(session, obj, context)
