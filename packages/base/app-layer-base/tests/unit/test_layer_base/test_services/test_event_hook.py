"""Unit tests for DomainEventHook."""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app_layer_base.base.schemas.delete_resp import DeleteResponse, MultipleDeleteResponse
from app_layer_base.base.services.base import BaseContextKwargs, BaseCreateServiceMixin
from app_layer_base.base.services.event_hook import DomainEventHook
from app_layer_base.base.services.hooks import Operation
from app_layer_base.core.database.transaction import run_after_commit
from test_layer_base.mock_models import MockCreateSchema, MockModel, MockRepository

# =============================================================================
# Concrete hooks for testing
# =============================================================================


class RecordingEventHook(DomainEventHook[MockModel, BaseContextKwargs]):
    """Records what it would have published."""

    def __init__(self):
        self.published: list[tuple[str, dict]] = []

    async def publish_event(self, topic: str, payload: dict[str, Any]) -> None:
        self.published.append((topic, payload))

    @property
    def topics(self) -> list[str]:
        return [topic for topic, _ in self.published]


class EnrichedEventHook(RecordingEventHook):
    """Overrides `payload` to prove the extension point is used."""

    def payload(self, op, event_type, pk, obj=None):
        base = super().payload(op, event_type, pk, obj)
        return {**base, "name": getattr(obj, "name", None)}


# =============================================================================
# Service wiring the hook, for the end-to-end checks
# =============================================================================


class EventCreateService(
    BaseCreateServiceMixin[MockRepository, MockModel, MockCreateSchema, BaseContextKwargs],
):
    def __init__(self, repo, hook):
        self._repo = repo
        self.hooks = (hook,)

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs


# =============================================================================
# Fixtures / helpers
# =============================================================================


@pytest.fixture
def hook():
    return RecordingEventHook()


@pytest.fixture
def composite_op(mock_async_session, composite_repo_mock) -> Operation:
    return Operation(session=mock_async_session, context={}, repo=composite_repo_mock)


def _row(repo, pk, **attrs) -> MagicMock:
    """A row whose pk columns carry `pk` (single value or composite tuple)."""
    obj = MagicMock()
    for col, value in zip(repo.primary_keys, repo.normalize_pk(pk), strict=True):
        setattr(obj, col.key, value)
    for key, value in attrs.items():
        setattr(obj, key, value)
    return obj


async def _publish(op: Operation, coro):
    """Await a `*_post` hook, then dispatch the after-commit publish it queued.

    DomainEventHook defers publishing until the transaction commits, so a test
    that wants to observe the event has to drain the after-commit queue itself --
    exactly what an owning AsyncTransaction does after a successful commit.
    """
    result = await coro
    await run_after_commit(op.session)
    return result


# =============================================================================
# Deferred-until-commit contract
# =============================================================================


class TestDomainEventDefersUntilCommit:
    async def test_create_post_publishes_nothing_before_commit(self, hook, base_op):
        """The payload is captured now, but publish waits for the commit drain."""
        await hook.create_post(base_op, _row(base_op.repo, uuid.uuid4()))

        assert hook.published == [], "event was published before the transaction committed"

        await run_after_commit(base_op.session)
        assert hook.topics == ["MockModel.created"]

    async def test_a_second_drain_does_not_republish(self, hook, base_op):
        """run_after_commit clears the queue, so re-draining is a no-op."""
        await _publish(base_op, hook.create_post(base_op, _row(base_op.repo, uuid.uuid4())))

        await run_after_commit(base_op.session)
        assert len(hook.published) == 1


# =============================================================================
# create
# =============================================================================


class TestDomainEventCreate:
    async def test_create_post_publishes_created(self, hook, base_op):
        obj_id = uuid.uuid4()

        returned = await _publish(base_op, hook.create_post(base_op, _row(base_op.repo, obj_id)))

        assert len(hook.published) == 1
        topic, payload = hook.published[0]
        assert topic == "MockModel.created"
        assert payload["event_type"] == "created"
        assert payload["resource_type"] == "MockModel"
        assert payload["resource_id"] == str(obj_id)
        assert returned is not None

    async def test_create_post_multi_publishes_one_aggregate_event(self, hook, base_op):
        objs = [_row(base_op.repo, uuid.uuid4()) for _ in range(3)]

        await _publish(base_op, hook.create_post_multi(base_op, objs))

        assert hook.topics == ["MockModel.created_multi"]
        _, payload = hook.published[0]
        assert payload["event_type"] == "created_multi"
        assert len(payload["resource_ids"]) == 3

    async def test_create_post_multi_publishes_nothing_for_an_empty_list(self, hook, base_op):
        await _publish(base_op, hook.create_post_multi(base_op, []))

        assert hook.published == []

    async def test_payload_override_is_used(self, base_op):
        enriched = EnrichedEventHook()

        await _publish(base_op, enriched.create_post(base_op, _row(base_op.repo, uuid.uuid4(), name="Widget")))

        _, payload = enriched.published[0]
        assert payload["name"] == "Widget"


# =============================================================================
# update
# =============================================================================


class TestDomainEventUpdate:
    async def test_update_post_publishes_updated(self, hook, base_op):
        obj_id = uuid.uuid4()

        await _publish(base_op, hook.update_post(base_op, _row(base_op.repo, obj_id)))

        assert len(hook.published) == 1
        topic, payload = hook.published[0]
        assert topic == "MockModel.updated"
        assert payload["event_type"] == "updated"
        assert payload["resource_id"] == str(obj_id)

    async def test_update_post_of_a_missing_row_publishes_nothing(self, hook, base_op):
        """No row was updated, so there is nothing to announce."""
        result = await _publish(base_op, hook.update_post(base_op, None))

        assert result is None
        assert hook.published == []


# =============================================================================
# delete
# =============================================================================


class TestDomainEventDelete:
    async def test_delete_post_publishes_deleted_on_success(self, hook, base_op, sample_uuid):
        result = await _publish(base_op, hook.delete_post(base_op, sample_uuid, DeleteResponse(success=True)))

        assert len(hook.published) == 1
        topic, payload = hook.published[0]
        assert topic == "MockModel.deleted"
        assert payload["event_type"] == "deleted"
        assert payload["resource_id"] == str(sample_uuid)
        assert result.success is True

    async def test_delete_post_publishes_nothing_on_failure(self, hook, base_op, sample_uuid):
        await _publish(base_op, hook.delete_post(base_op, sample_uuid, DeleteResponse(success=False)))

        assert hook.published == []

    async def test_delete_post_multi_publishes_one_aggregate_event(self, hook, base_op):
        pks = [uuid.uuid4(), uuid.uuid4()]

        await _publish(base_op, hook.delete_post_multi(base_op, pks, MultipleDeleteResponse(deleted_count=2)))

        assert hook.topics == ["MockModel.deleted_multi"]
        _, payload = hook.published[0]
        assert payload["event_type"] == "deleted_multi"
        assert payload["resource_ids"] == [str(pk) for pk in pks]

    async def test_delete_post_multi_publishes_nothing_when_nothing_was_deleted(self, hook, base_op):
        await _publish(base_op, hook.delete_post_multi(base_op, [], MultipleDeleteResponse(deleted_count=0)))

        assert hook.published == []


# =============================================================================
# Composite primary keys
# =============================================================================


class TestDomainEventCompositePk:
    async def test_created_event_joins_the_key_parts_with_a_comma(self, hook, composite_op):
        tenant = uuid.uuid4()

        await _publish(composite_op, hook.create_post(composite_op, _row(composite_op.repo, (tenant, "A"))))

        _, payload = hook.published[0]
        assert payload["resource_id"] == f"{tenant},A"
        assert payload["resource_type"] == "MockCompositeModel"

    async def test_deleted_multi_event_joins_every_key(self, hook, composite_op):
        tenant = uuid.uuid4()
        pks = [(tenant, "A"), (tenant, "B")]

        await _publish(composite_op, hook.delete_post_multi(composite_op, pks, MultipleDeleteResponse(deleted_count=2)))

        _, payload = hook.published[0]
        assert payload["resource_ids"] == [f"{tenant},A", f"{tenant},B"]


# =============================================================================
# End-to-end through a service
# =============================================================================


class TestDomainEventThroughService:
    async def test_create_publishes_after_the_row_exists(self, mock_repo, mock_async_session):
        hook = RecordingEventHook()
        service = EventCreateService(mock_repo, hook)
        obj_id = uuid.uuid4()
        mock_repo.create = AsyncMock(return_value=_row(mock_repo, obj_id))

        await service.create(mock_async_session, MockCreateSchema(name="x"))
        assert hook.published == [], "service.create must not publish before its transaction commits"

        await run_after_commit(mock_async_session)
        assert hook.topics == ["MockModel.created"]
        assert hook.published[0][1]["resource_id"] == str(obj_id)

    async def test_create_multi_publishes_a_single_event(self, mock_repo, mock_async_session):
        hook = RecordingEventHook()
        service = EventCreateService(mock_repo, hook)
        objs = [_row(mock_repo, uuid.uuid4()) for _ in range(2)]
        mock_repo.create_multi = AsyncMock(return_value=objs)

        await service.create_multi(mock_async_session, [MockCreateSchema(name="a"), MockCreateSchema(name="b")])
        await run_after_commit(mock_async_session)

        assert hook.topics == ["MockModel.created_multi"]
