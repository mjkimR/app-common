import abc
from collections.abc import Sequence
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.schemas.delete_resp import DeleteResponse, MultipleDeleteResponse
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateHooks,
    BaseDeleteHooks,
    BaseUpdateHooks,
)


class DomainEventHooksMixin[ModelType: Any, TContextKwargs: BaseContextKwargs](
    BaseCreateHooks[ModelType, TContextKwargs],
    BaseUpdateHooks[ModelType, TContextKwargs],
    BaseDeleteHooks[TContextKwargs],
    metaclass=abc.ABCMeta,
):
    """
    A base hook that publishes domain events after CUD (Create, Update, Delete) operations are completed.
    By default, it publishes the resource ID to topics such as 'ModelName.created'.
    """

    @abc.abstractmethod
    async def publish_event(self, topic: str, payload: dict[str, Any]) -> None:
        # Example: await self.event_bus.publish(topic, payload)
        pass

    # ============================================================
    # PK Helpers
    # ============================================================

    def _get_pk_from_obj(self, obj: ModelType) -> PrimaryKeyType:
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
        return ",".join(pk_tuple)

    # ============================================================
    # Hooks
    # ============================================================

    def _get_event_payload(
        self, event_type: str, obj_pk: PrimaryKeyType, obj: ModelType | None = None
    ) -> dict[str, Any]:
        """
        Get the event payload.

        The default payload only includes the resource ID and event type.
        If necessary, override this method in a child class to include more information.
        """
        return {
            "resource_id": self._pk_to_string(obj_pk),
            "resource_type": self.repo.model_name(),
            "event_type": event_type,
        }

    async def _post_create(self, session: AsyncSession, obj: ModelType, context: TContextKwargs) -> ModelType:
        """
        Publish a domain event after an object is created.
        """
        obj = await super()._post_create(session, obj, context)
        topic = f"{self.repo.model_name()}.created"

        obj_pk = self._get_pk_from_obj(obj)
        payload = self._get_event_payload("created", obj_pk, obj)
        await self.publish_event(topic, payload)

        return obj

    async def _post_create_multi(
        self, session: AsyncSession, objs: Sequence[ModelType], context: TContextKwargs
    ) -> Sequence[ModelType]:
        """
        Publish a single bulk domain event after multiple objects are created.
        """
        objs = await super()._post_create_multi(session, objs, context)
        if objs:
            topic = f"{self.repo.model_name()}.created_multi"
            payload = {
                "resource_ids": [self._pk_to_string(self._get_pk_from_obj(obj)) for obj in objs],
                "resource_type": self.repo.model_name(),
                "event_type": "created_multi",
            }
            await self.publish_event(topic, payload)
        return objs

    async def _post_update(
        self, session: AsyncSession, obj: ModelType | None, context: TContextKwargs, partial: bool = True
    ) -> ModelType | None:
        """
        Publish a domain event after an object is updated.
        """
        obj = await super()._post_update(session, obj, context, partial=partial)
        if obj is None:
            return None

        topic = f"{self.repo.model_name()}.updated"
        obj_pk = self._get_pk_from_obj(obj)
        payload = self._get_event_payload("updated", obj_pk, obj)
        await self.publish_event(topic, payload)

        return obj

    async def _post_delete(
        self,
        session: AsyncSession,
        obj_pk: PrimaryKeyType,
        result: DeleteResponse,
        context: TContextKwargs,
    ) -> DeleteResponse:
        """
        Publish a domain event after an object is deleted.
        """
        result = await super()._post_delete(session, obj_pk, result, context)

        if result.success:
            topic = f"{self.repo.model_name()}.deleted"
            payload = self._get_event_payload("deleted", obj_pk)
            await self.publish_event(topic, payload)

        return result

    async def _post_delete_multi(
        self,
        session: AsyncSession,
        obj_pks: Sequence[PrimaryKeyType],
        result: MultipleDeleteResponse,
        context: TContextKwargs,
    ) -> MultipleDeleteResponse:
        """
        Publish a single bulk domain event after multiple objects are deleted.
        """
        result = await super()._post_delete_multi(session, obj_pks, result, context)
        if result.deleted_count > 0:
            topic = f"{self.repo.model_name()}.deleted_multi"
            payload = {
                "resource_ids": [self._pk_to_string(pk) for pk in obj_pks],
                "resource_type": self.repo.model_name(),
                "event_type": "deleted_multi",
            }
            await self.publish_event(topic, payload)
        return result
