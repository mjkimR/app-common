import abc
import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app_base.base.schemas.delete_resp import DeleteResponse
from app_base.base.services.base import (
    BaseCreateHooks,
    BaseDeleteHooks,
    BaseUpdateHooks,
    ModelType,
    TContextKwargs,
)


class DomainEventHooksMixin(BaseCreateHooks, BaseUpdateHooks, BaseDeleteHooks, metaclass=abc.ABCMeta):
    """
    A base hook that publishes domain events after CUD (Create, Update, Delete) operations are completed.
    By default, it publishes the resource ID to topics such as 'ModelName.created'.
    """

    @abc.abstractmethod
    async def publish_event(self, topic: str, payload: dict[str, Any]) -> None:
        # Example: await self.event_bus.publish(topic, payload)
        pass

    def _get_event_payload(self, event_type: str, obj_id: uuid.UUID, obj: Optional[ModelType] = None) -> dict[str, Any]:
        """
        Get the event payload.

        The default payload only includes the resource ID and event type.
        If necessary, override this method in a child class to include more information.
        """
        return {
            "resource_id": str(obj_id),
            "resource_type": self.repo.model_name(),
            "event_type": event_type,
        }

    async def _post_create(self, session: AsyncSession, obj: ModelType, context: TContextKwargs) -> ModelType:
        """
        Publish a domain event after an object is created.
        """
        obj = await super()._post_create(session, obj, context)
        topic = f"{self.repo.model_name()}.created"
        payload = self._get_event_payload("created", obj.id, obj)
        await self.publish_event(topic, payload)

        return obj

    async def _post_update(self, session: AsyncSession, obj: ModelType, context: TContextKwargs) -> ModelType:
        """
        Publish a domain event after an object is updated.
        """
        obj = await super()._post_update(session, obj, context)

        topic = f"{self.repo.model_name()}.updated"
        payload = self._get_event_payload("updated", obj.id, obj)
        await self.publish_event(topic, payload)

        return obj

    async def _post_delete(
        self,
        session: AsyncSession,
        obj_id: uuid.UUID,
        result: DeleteResponse,
        context: TContextKwargs,
    ) -> DeleteResponse:
        """
        Publish a domain event after an object is deleted.
        """
        result = await super()._post_delete(session, obj_id, result, context)

        if result.success:
            topic = f"{self.repo.model_name()}.deleted"
            payload = self._get_event_payload("deleted", obj_id)
            await self.publish_event(topic, payload)

        return result
