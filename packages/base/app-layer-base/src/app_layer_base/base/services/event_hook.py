import abc
from collections.abc import Sequence
from typing import Any

from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.schemas.delete_resp import DeleteResponse, MultipleDeleteResponse
from app_layer_base.base.services.hooks import (
    BaseContextKwargs,
    CreateHook,
    DeleteHook,
    Operation,
    UpdateHook,
)


class DomainEventHook[ModelType: Any, TContextKwargs: BaseContextKwargs](
    CreateHook[ModelType, TContextKwargs],
    UpdateHook[ModelType, TContextKwargs],
    DeleteHook[TContextKwargs],
    metaclass=abc.ABCMeta,
):
    """
    Publishes a domain event after each CUD operation, e.g. 'Book.created'.

    Publishing is deferred to *after the transaction commits* via
    ``op.register_after_commit``: the payload is captured while the row is in hand,
    but ``publish_event`` only fires once the write is durable. A hook that
    published inline would emit even when the surrounding transaction later rolls
    back (a dual write). The trade-off is honest at-most-once delivery -- if a
    publish fails the event is logged and lost. When the event must not be lost,
    use ``OutboxHook`` (writes the event in the same transaction) instead.

    Bulk operations publish one aggregate event ('Book.created_multi') instead of
    one per item -- that override replaces only this hook's per-item publishing.
    Other hooks still run per item.
    """

    @abc.abstractmethod
    async def publish_event(self, topic: str, payload: dict[str, Any]) -> None:
        """[Override Required] e.g. await self.event_bus.publish(topic, payload)"""

    # ============================================================
    # PK Helpers
    # ============================================================

    def _get_pk_from_obj(self, op: Operation[TContextKwargs], obj: ModelType) -> PrimaryKeyType:
        """Extracts the primary key value(s) from a given model object dynamically."""
        pk_cols = op.repo.primary_keys
        if len(pk_cols) == 1:
            return getattr(obj, pk_cols[0].key)
        return tuple(getattr(obj, col.key) for col in pk_cols)

    def _pk_to_string(self, op: Operation[TContextKwargs], pk: PrimaryKeyType) -> str:
        """Composite keys are comma-separated."""
        return ",".join(op.repo.normalize_pk_as_str(pk))

    def payload(
        self,
        op: Operation[TContextKwargs],
        event_type: str,
        pk: PrimaryKeyType,
        obj: ModelType | None = None,
    ) -> dict[str, Any]:
        """
        The event payload.

        Defaults to the resource id and event type. Override to add more.
        """
        return {
            "resource_id": self._pk_to_string(op, pk),
            "resource_type": op.repo.model_name(),
            "event_type": event_type,
        }

    def _bulk_payload(
        self, op: Operation[TContextKwargs], event_type: str, pks: Sequence[PrimaryKeyType]
    ) -> dict[str, Any]:
        return {
            "resource_ids": [self._pk_to_string(op, pk) for pk in pks],
            "resource_type": op.repo.model_name(),
            "event_type": event_type,
        }

    # ============================================================
    # Hooks
    # ============================================================

    def _defer_publish(self, op: Operation[TContextKwargs], topic: str, payload: dict[str, Any]) -> None:
        """Publish ``topic`` after the transaction commits (see the class docstring)."""
        op.register_after_commit(lambda: self.publish_event(topic, payload))

    async def create_post(self, op: Operation[TContextKwargs], obj: ModelType) -> ModelType:
        pk = self._get_pk_from_obj(op, obj)
        self._defer_publish(op, f"{op.repo.model_name()}.created", self.payload(op, "created", pk, obj))
        return obj

    async def create_post_multi(self, op: Operation[TContextKwargs], objs: Sequence[ModelType]) -> Sequence[ModelType]:
        """One aggregate event instead of one per item."""
        if objs:
            pks = [self._get_pk_from_obj(op, obj) for obj in objs]
            self._defer_publish(
                op,
                f"{op.repo.model_name()}.created_multi",
                self._bulk_payload(op, "created_multi", pks),
            )
        return objs

    async def update_post(
        self, op: Operation[TContextKwargs], obj: ModelType | None, partial: bool = True
    ) -> ModelType | None:
        if obj is None:
            return None

        pk = self._get_pk_from_obj(op, obj)
        self._defer_publish(op, f"{op.repo.model_name()}.updated", self.payload(op, "updated", pk, obj))
        return obj

    async def delete_post(
        self, op: Operation[TContextKwargs], pk: PrimaryKeyType, result: DeleteResponse
    ) -> DeleteResponse:
        if result.success:
            self._defer_publish(op, f"{op.repo.model_name()}.deleted", self.payload(op, "deleted", pk))
        return result

    async def delete_post_multi(
        self,
        op: Operation[TContextKwargs],
        pks: Sequence[PrimaryKeyType],
        result: MultipleDeleteResponse,
    ) -> MultipleDeleteResponse:
        """One aggregate event instead of one per item."""
        if result.deleted_count > 0:
            self._defer_publish(
                op,
                f"{op.repo.model_name()}.deleted_multi",
                self._bulk_payload(op, "deleted_multi", pks),
            )
        return result
