from abc import ABCMeta, abstractmethod
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import Any, TypedDict

from app_layer_base.base.repos.base import PrimaryKeyType
from app_layer_base.base.schemas.delete_resp import DeleteResponse, MultipleDeleteResponse
from app_layer_base.base.services.hooks import (
    BaseContextKwargs,
    CreateHook,
    DeleteHook,
    Operation,
    UpdateHook,
)
from sqlalchemy import tuple_

from .repos import OutboxRepository
from .schemas import OutboxCreate, OutboxIdentityDict


class OutboxHookEventTypeDict(TypedDict):
    CREATE: str
    UPDATE: str
    DELETE: str


class OutboxHook[ModelType: Any, TContextKwargs: BaseContextKwargs](
    CreateHook[ModelType, TContextKwargs],
    UpdateHook[ModelType, TContextKwargs],
    DeleteHook[TContextKwargs],
    metaclass=ABCMeta,
):
    """
    Writes an outbox row in the same transaction as the change that caused it.

    One row per changed object, including on create_multi -- there is no bulk
    form, because collapsing N changes into one outbox row would lose events.

        class BookOutboxHook(OutboxHook[Book, BaseContextKwargs]):
            def payload(self, op, obj, identity):
                return {"title": obj.title}

        class BookService(BaseCreateServiceMixin, ...):
            @cached_property
            def hooks(self):
                return (BookOutboxHook(self.outbox_repo, BOOK_EVENTS),)
    """

    def __init__(self, outbox_repo: OutboxRepository, event_types: OutboxHookEventTypeDict):
        self.outbox_repo = outbox_repo
        self.event_types = event_types

    @abstractmethod
    def payload(
        self,
        op: Operation[TContextKwargs],
        obj: ModelType,
        identity: OutboxIdentityDict,
    ) -> dict[str, Any]:
        """[Override Required] JSON-serializable payload for the outbox event."""

    # ============================================================
    # Helpers
    # ============================================================

    def _get_pk_from_obj(self, op: Operation[TContextKwargs], obj: ModelType) -> PrimaryKeyType:
        pk_cols = op.repo.primary_keys
        if len(pk_cols) == 1:
            return getattr(obj, pk_cols[0].key)
        return tuple(getattr(obj, col.key) for col in pk_cols)

    def _pk_to_string(self, op: Operation[TContextKwargs], pk: PrimaryKeyType) -> str:
        pk_values = list(op.repo.normalize_pk_as_str(pk))
        if not pk_values:
            raise ValueError("Primary key value is required.")
        return ",".join(pk_values)

    def _identity(self, op: Operation[TContextKwargs], pk: PrimaryKeyType, event_type: str) -> OutboxIdentityDict:
        return {
            "aggregate_type": op.repo.model_name(),
            "aggregate_id": self._pk_to_string(op, pk),
            "event_type": event_type,
        }

    async def _record(
        self, op: Operation[TContextKwargs], identity: OutboxIdentityDict, payload: dict[str, Any]
    ) -> None:
        await self.outbox_repo.create(
            session=op.session,
            obj_in=OutboxCreate(**identity, payload=payload),
        )

    # ---- delete: the row must be read before it is gone, but the event may
    # ---- only be written once the delete is known to have happened.

    _CAPTURED = "outbox_pending_delete"

    def _key(self, op: Operation[TContextKwargs], pk: PrimaryKeyType) -> tuple[str, ...]:
        """A hashable pk that compares equal across UUID/str."""
        return op.repo.normalize_pk_as_str(pk)

    def _captured(
        self, op: Operation[TContextKwargs]
    ) -> dict[tuple[str, ...], tuple[OutboxIdentityDict, dict[str, Any]]]:
        return op.state.setdefault(self._CAPTURED, {})

    def _capture(self, op: Operation[TContextKwargs], pk: PrimaryKeyType, obj: ModelType) -> None:
        identity = self._identity(op, pk, self.event_types["DELETE"])
        self._captured(op)[self._key(op, pk)] = (identity, self.payload(op, obj, identity))

    def _pk_in(self, op: Operation[TContextKwargs], pks: Sequence[PrimaryKeyType]):
        pk_cols = op.repo.primary_keys
        if len(pk_cols) == 1:
            return pk_cols[0].in_([op.repo.normalize_pk(pk)[0] for pk in pks])
        return tuple_(*pk_cols).in_([op.repo.normalize_pk(pk) for pk in pks])

    # ============================================================
    # Hooks
    # ============================================================

    async def create_post(self, op: Operation[TContextKwargs], obj: ModelType) -> ModelType:
        identity = self._identity(op, self._get_pk_from_obj(op, obj), self.event_types["CREATE"])
        await self._record(op, identity, self.payload(op, obj, identity))
        return obj

    async def update_post(
        self, op: Operation[TContextKwargs], obj: ModelType | None, partial: bool = True
    ) -> ModelType | None:
        if obj is None:
            return None

        identity = self._identity(op, self._get_pk_from_obj(op, obj), self.event_types["UPDATE"])
        await self._record(op, identity, self.payload(op, obj, identity))
        return obj

    @asynccontextmanager
    async def delete_context(self, op: Operation[TContextKwargs], pk: PrimaryKeyType) -> AsyncGenerator[None]:
        """Read the row while it still exists; the event is written in delete_post."""
        obj = await op.repo.get_by_pk(op.session, pk)
        if obj is not None:
            self._capture(op, pk, obj)
        yield

    async def delete_post(
        self, op: Operation[TContextKwargs], pk: PrimaryKeyType, result: DeleteResponse
    ) -> DeleteResponse:
        """Write the event only for a row that really was deleted."""
        captured = self._captured(op).pop(self._key(op, pk), None)
        if result.success and captured is not None:
            identity, payload = captured
            await self._record(op, identity, payload)
        return result

    @asynccontextmanager
    async def delete_context_multi(
        self, op: Operation[TContextKwargs], pks: Sequence[PrimaryKeyType]
    ) -> AsyncGenerator[None]:
        """Replaces this hook's per-item read with a single IN query."""
        if pks:
            for obj in await op.repo.get_all(op.session, where=[self._pk_in(op, pks)]):
                self._capture(op, self._get_pk_from_obj(op, obj), obj)
        yield

    async def delete_post_multi(
        self,
        op: Operation[TContextKwargs],
        pks: Sequence[PrimaryKeyType],
        result: MultipleDeleteResponse,
    ) -> MultipleDeleteResponse:
        """
        One event per row that really was deleted.

        MultipleDeleteResponse only carries a count, so on a partial delete the
        surviving rows are re-read: whatever is still there was not deleted and
        must not get an event.
        """
        if not pks:
            return result

        survivors: set[tuple[str, ...]] = set()
        if result.deleted_count != len(pks):
            remaining = await op.repo.get_all(op.session, where=[self._pk_in(op, pks)])
            survivors = {self._key(op, self._get_pk_from_obj(op, obj)) for obj in remaining}

        for pk in pks:
            deleted = self._key(op, pk) not in survivors
            await self.delete_post(op, pk, DeleteResponse(success=deleted, identity=pk))
        return result
