from abc import abstractmethod
from contextlib import asynccontextmanager
from typing import Any, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app_base.base.repos.base import PrimaryKeyType
from app_base.base.services.base import (
    BaseCreateHooks,
    BaseDeleteHooks,
    BaseUpdateHooks,
    ModelType,
    TContextKwargs,
)

from .repos import OutboxRepository
from .schemas import OutboxCreate, OutboxIdentityDict


class OutboxHookEventTypeDict(TypedDict):
    CREATE: str
    UPDATE: str
    DELETE: str


class BaseOutboxHook(
    BaseCreateHooks,
    BaseUpdateHooks,
    BaseDeleteHooks,
):
    @abstractmethod
    def _get_outbox_payload(
        self,
        obj: Any,
        context: TContextKwargs,
        outbox_identity: OutboxIdentityDict,
    ) -> dict[str, Any]:
        """
        Generate the notification payload for outbox events.
        JSON-serializable dictionary containing the notification payload.
        """
        pass

    @property
    @abstractmethod
    def outbox_repo(self) -> OutboxRepository:
        pass

    @property
    @abstractmethod
    def _event_type_dict(self) -> OutboxHookEventTypeDict:
        pass

    # ============================================================
    # PK Helpers
    # ============================================================

    def _get_pk_from_obj(self, obj: Any) -> PrimaryKeyType:
        """Extracts the primary key value(s) from a given model object dynamically."""
        pk_cols = self.repo.primary_keys
        if len(pk_cols) == 1:
            return getattr(obj, pk_cols[0].key)
        return tuple(getattr(obj, col.key) for col in pk_cols)

    def _pk_to_string(self, pk: PrimaryKeyType) -> str:
        """
        Converts a single or composite primary key into a string for event payloads.
        Composite keys will be comma-separated.
        """
        pk_tuple = self.repo.normalize_pk_as_str(pk)
        return ",".join(pk_tuple) if len(pk_tuple) > 1 else pk_tuple[0]

    # ============================================================
    # Hooks
    # ============================================================

    async def _post_create(self, session: AsyncSession, obj: ModelType, context: TContextKwargs) -> ModelType:
        """Create outbox event after creation of the object."""
        obj_pk = self._get_pk_from_obj(obj)
        outbox_identity: OutboxIdentityDict = {
            "aggregate_type": self.repo.model_name(),
            "aggregate_id": self._pk_to_string(obj_pk),
            "event_type": self._event_type_dict["CREATE"],
        }
        await self.outbox_repo.create(
            session=session,
            obj_in=OutboxCreate(
                **outbox_identity,
                payload=self._get_outbox_payload(obj, context, outbox_identity),
            ),
        )

        return await super()._post_create(session, obj, context)

    async def _post_update(
        self, session: AsyncSession, obj: ModelType, context: TContextKwargs, partial: bool = True
    ) -> ModelType:
        """Create outbox event after update."""
        obj_pk = self._get_pk_from_obj(obj)
        outbox_identity: OutboxIdentityDict = {
            "aggregate_type": self.repo.model_name(),
            "aggregate_id": self._pk_to_string(obj_pk),
            "event_type": self._event_type_dict["UPDATE"],
        }
        await self.outbox_repo.create(
            session=session,
            obj_in=OutboxCreate(
                **outbox_identity,
                payload=self._get_outbox_payload(obj, context, outbox_identity),
            ),
        )

        return await super()._post_update(session, obj, context, partial=partial)

    @asynccontextmanager
    async def _context_delete(self, session: AsyncSession, obj_pk: PrimaryKeyType, context: TContextKwargs):
        """Use context manager to ensure outbox event is created after deletion."""
        async with super()._context_delete(session, obj_pk, context):
            obj = await self.repo.get_by_pk(session, obj_pk)
            outbox_identity: OutboxIdentityDict = {
                "aggregate_type": self.repo.model_name(),
                "aggregate_id": self._pk_to_string(obj_pk),
                "event_type": self._event_type_dict["DELETE"],
            }

            if obj:
                payload = self._get_outbox_payload(obj, context, outbox_identity)
            else:
                payload = None

            yield

            if payload is not None:
                await self.outbox_repo.create(
                    session=session,
                    obj_in=OutboxCreate(
                        **outbox_identity,
                        payload=payload,
                    ),
                )
