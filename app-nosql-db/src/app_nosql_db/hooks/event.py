import abc
from typing import Any

from app_layer_base.base.schemas.delete_resp import DeleteResponse

from app_nosql_db.hooks.base import (
    BaseNoSQLContextKwargs,
    BaseNoSQLCreateHooks,
    BaseNoSQLDeleteHooks,
    BaseNoSQLUpdateHooks,
)
from app_nosql_db.interface import NoSQLDBProvider


class NoSQLDomainEventHooksMixin[ModelType: Any, TContextKwargs: BaseNoSQLContextKwargs](
    BaseNoSQLCreateHooks[ModelType, TContextKwargs],
    BaseNoSQLUpdateHooks[ModelType, TContextKwargs],
    BaseNoSQLDeleteHooks[TContextKwargs],
    metaclass=abc.ABCMeta,
):
    """
    A base hook that publishes domain events after NoSQL CUD (Create, Update, Delete) operations are completed.
    """

    @abc.abstractmethod
    async def publish_event(self, topic: str, payload: dict[str, Any]) -> None:
        pass

    def _get_event_payload(self, event_type: str, document_id: str, obj: ModelType | None = None) -> dict[str, Any]:
        return {
            "resource_id": document_id,
            "resource_type": self.repo.model_name(),
            "event_type": event_type,
        }

    async def _post_create(self, provider: NoSQLDBProvider, obj: ModelType, context: TContextKwargs) -> ModelType:
        obj = await super()._post_create(provider, obj, context)
        topic = f"{self.repo.model_name()}.created"
        doc_id = getattr(obj, "id", "unknown")
        payload = self._get_event_payload("created", doc_id, obj)
        await self.publish_event(topic, payload)

        return obj

    async def _post_update(
        self, provider: NoSQLDBProvider, obj: ModelType | None, context: TContextKwargs, partial: bool = True
    ) -> ModelType | None:
        obj = await super()._post_update(provider, obj, context, partial)
        if obj is None:
            return None

        topic = f"{self.repo.model_name()}.updated"
        doc_id = getattr(obj, "id", "unknown")
        payload = self._get_event_payload("updated", doc_id, obj)
        await self.publish_event(topic, payload)

        return obj

    async def _post_delete(
        self,
        provider: NoSQLDBProvider,
        document_id: str,
        result: DeleteResponse,
        context: TContextKwargs,
    ) -> DeleteResponse:
        result = await super()._post_delete(provider, document_id, result, context)

        if result.success:
            topic = f"{self.repo.model_name()}.deleted"
            payload = self._get_event_payload("deleted", document_id)
            await self.publish_event(topic, payload)

        return result
