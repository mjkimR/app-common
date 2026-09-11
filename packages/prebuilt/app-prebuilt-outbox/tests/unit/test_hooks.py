"""
Unit tests for OutboxHook.

The hook writes one outbox row per changed object, in the same session as the
change. Two levels are covered here:

* the hook in isolation -- one row per create/update/delete, with the right
  identity and payload, and nothing at all when there is no object;
* the hook mounted on a service, because an outbox is only correct if the
  *executor* still reaches it. ``create_multi`` in particular must produce N rows,
  and must keep producing N rows when another hook on the same service collapses
  the bulk path into a single aggregate event.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app_layer_base.base.schemas.delete_resp import DeleteResponse, MultipleDeleteResponse
from app_layer_base.base.services.base import (
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseUpdateServiceMixin,
)
from app_layer_base.base.services.event_hook import DomainEventHook
from app_layer_base.base.services.hooks import BaseContextKwargs, Operation
from app_layer_base.core.database.transaction import run_after_commit
from app_prebuilt_outbox.hooks import OutboxHook
from pydantic import BaseModel

EVENT_TYPES = {"CREATE": "ITEM_CREATED", "UPDATE": "ITEM_UPDATED", "DELETE": "ITEM_DELETED"}


# =============================================================================
# Test doubles
# =============================================================================


class ItemCreate(BaseModel):
    name: str


class ItemUpdate(BaseModel):
    name: str | None = None


class ConcreteOutboxHook(OutboxHook[Any, BaseContextKwargs]):
    """Minimal concrete hook: only the payload is required."""

    def payload(self, op, obj, identity):
        return {"id": identity["aggregate_id"], "name": getattr(obj, "name", None)}


class AggregateEventHook(DomainEventHook[Any, BaseContextKwargs]):
    """
    Overrides the bulk path: one aggregate event for create_multi instead of one
    per item. Collapsing its own work must not collapse the outbox's.
    """

    def __init__(self):
        self.published: list[str] = []

    async def publish_event(self, topic: str, payload: dict) -> None:
        self.published.append(topic)


class ItemService(
    BaseCreateServiceMixin,
    BaseUpdateServiceMixin,
    BaseDeleteServiceMixin,
):
    def __init__(self, repo, hooks):
        self._repo = repo
        self.hooks = hooks

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs


def make_repo() -> MagicMock:
    """An aggregate-repo mock with a single `id` primary key."""
    repo = MagicMock()
    pk_col = MagicMock()
    pk_col.key = "id"
    repo.primary_keys = [pk_col]
    repo.model_name.return_value = "Item"
    repo.normalize_pk.side_effect = lambda pk: (pk,)
    repo.normalize_pk_as_str.side_effect = lambda pk: (str(pk),)
    repo.model_repr.side_effect = lambda pk: f"Item(id={pk})"
    return repo


def make_item(name: str = "widget") -> MagicMock:
    obj = MagicMock()
    obj.id = uuid.uuid4()
    obj.name = name
    return obj


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def obj():
    return make_item()


@pytest.fixture
def obj_id(obj):
    return obj.id


@pytest.fixture
def objs():
    return [make_item(f"widget-{i}") for i in range(3)]


@pytest.fixture
def repo():
    return make_repo()


@pytest.fixture
def outbox_repo():
    outbox_repo = MagicMock()
    outbox_repo.create = AsyncMock()
    return outbox_repo


@pytest.fixture
def hook(outbox_repo):
    return ConcreteOutboxHook(outbox_repo, EVENT_TYPES)


@pytest.fixture
def session():
    session = AsyncMock()
    # A real dict so DomainEventHook's register_after_commit can queue on session.info.
    session.info = {}
    return session


@pytest.fixture
def op(session, repo):
    return Operation(session=session, context={}, repo=repo)


# =============================================================================
# Helpers
# =============================================================================


def _rows(outbox_repo) -> list:
    """Every OutboxCreate passed to outbox_repo.create, in order."""
    return [call.kwargs["obj_in"] for call in outbox_repo.create.await_args_list]


def _row(outbox_repo):
    """The single OutboxCreate passed to outbox_repo.create."""
    rows = _rows(outbox_repo)
    assert len(rows) == 1, f"expected exactly one outbox row, got {len(rows)}"
    return rows[0]


# =============================================================================
# The hook on its own
# =============================================================================


class TestOutboxHook:
    async def test_create_post_emits_created_event(self, hook, outbox_repo, op, obj, obj_id):
        await hook.create_post(op, obj)

        row = _row(outbox_repo)
        assert row.aggregate_type == "Item"
        assert row.aggregate_id == str(obj_id)
        assert row.event_type == "ITEM_CREATED"
        assert row.payload == {"id": str(obj_id), "name": "widget"}

    async def test_create_post_returns_the_object(self, hook, op, obj):
        assert await hook.create_post(op, obj) is obj

    async def test_update_post_emits_updated_event(self, hook, outbox_repo, op, obj, obj_id):
        await hook.update_post(op, obj)

        row = _row(outbox_repo)
        assert row.aggregate_type == "Item"
        assert row.event_type == "ITEM_UPDATED"
        assert row.aggregate_id == str(obj_id)
        assert row.payload == {"id": str(obj_id), "name": "widget"}

    async def test_update_post_writes_nothing_when_the_row_did_not_exist(self, hook, outbox_repo, op):
        """`repo.update_by_pk` returns None for a missing pk: no event, no AttributeError."""
        result = await hook.update_post(op, None)

        assert result is None
        outbox_repo.create.assert_not_awaited()

    async def test_delete_emits_deleted_event(self, hook, outbox_repo, op, repo, obj, obj_id):
        """delete_context only reads the row; delete_post writes the event."""
        repo.get_by_pk = AsyncMock(return_value=obj)

        async with hook.delete_context(op, obj_id):
            outbox_repo.create.assert_not_awaited()

        await hook.delete_post(op, obj_id, DeleteResponse(success=True, identity=obj_id))

        row = _row(outbox_repo)
        assert row.aggregate_type == "Item"
        assert row.event_type == "ITEM_DELETED"
        assert row.aggregate_id == str(obj_id)
        assert row.payload == {"id": str(obj_id), "name": "widget"}

    async def test_delete_writes_no_event_when_the_row_was_not_deleted(self, hook, outbox_repo, op, repo, obj, obj_id):
        """The row existed when we read it, but the delete did not take (e.g. a lost race)."""
        repo.get_by_pk = AsyncMock(return_value=obj)

        async with hook.delete_context(op, obj_id):
            pass
        await hook.delete_post(op, obj_id, DeleteResponse(success=False, identity=obj_id))

        outbox_repo.create.assert_not_awaited()

    async def test_delete_context_skips_when_object_missing(self, hook, outbox_repo, op, repo, obj_id):
        repo.get_by_pk = AsyncMock(return_value=None)

        async with hook.delete_context(op, obj_id):
            pass

        outbox_repo.create.assert_not_awaited()

    async def test_delete_multi_only_emits_for_rows_that_were_actually_deleted(self, hook, outbox_repo, op, repo):
        """
        A partial delete must not invent events. MultipleDeleteResponse only carries
        a count, so the surviving rows are re-read: whatever is still there gets no event.
        """
        pks = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
        rows = []
        for pk in pks:
            row = MagicMock()
            row.id = pk
            row.name = "widget"
            rows.append(row)

        # 1st get_all: capture (all three still present).
        # 2nd get_all: survivors after the delete -- only pks[0] actually went.
        repo.get_all = AsyncMock(side_effect=[rows, [rows[1], rows[2]]])

        async with hook.delete_context_multi(op, pks):
            pass
        await hook.delete_post_multi(op, pks, MultipleDeleteResponse(deleted_count=1, failed_count=2))

        written = [r.aggregate_id for r in _rows(outbox_repo)]
        assert written == [str(pks[0])], "an event was emitted for a row that still exists"


# =============================================================================
# The hook mounted on a service
# =============================================================================


class TestOutboxHookOnAService:
    async def test_create_writes_one_row(self, repo, outbox_repo, hook, session, obj, obj_id):
        repo.create = AsyncMock(return_value=obj)
        service = ItemService(repo, (hook,))

        await service.create(session, ItemCreate(name="widget"))

        row = _row(outbox_repo)
        assert row.aggregate_id == str(obj_id)
        assert row.event_type == "ITEM_CREATED"

    async def test_patch_writes_one_row(self, repo, outbox_repo, hook, session, obj, obj_id):
        repo.update_by_pk = AsyncMock(return_value=obj)
        service = ItemService(repo, (hook,))

        await service.patch(session, obj_id, ItemUpdate(name="widget"))

        row = _row(outbox_repo)
        assert row.aggregate_id == str(obj_id)
        assert row.event_type == "ITEM_UPDATED"

    async def test_patch_of_a_missing_row_writes_nothing_and_does_not_raise(self, repo, outbox_repo, hook, session):
        repo.update_by_pk = AsyncMock(return_value=None)  # pk does not exist
        service = ItemService(repo, (hook,))

        result = await service.patch(session, uuid.uuid4(), ItemUpdate(name="ghost"))

        assert result is None
        outbox_repo.create.assert_not_awaited()

    async def test_delete_writes_one_row(self, repo, outbox_repo, hook, session, obj, obj_id):
        repo.get_by_pk = AsyncMock(return_value=obj)
        repo.delete_by_pk = AsyncMock(return_value=True)
        service = ItemService(repo, (hook,))

        await service.delete(session, obj_id)

        row = _row(outbox_repo)
        assert row.aggregate_id == str(obj_id)
        assert row.event_type == "ITEM_DELETED"

    async def test_delete_of_a_missing_row_writes_nothing(self, repo, outbox_repo, hook, session):
        repo.get_by_pk = AsyncMock(return_value=None)
        repo.delete_by_pk = AsyncMock(return_value=False)
        service = ItemService(repo, (hook,))

        await service.delete(session, uuid.uuid4())

        outbox_repo.create.assert_not_awaited()

    async def test_create_multi_writes_one_row_per_object(self, repo, outbox_repo, hook, session, objs):
        """N objects means N events. An outbox that collapses them into one loses events."""
        repo.create_multi = AsyncMock(return_value=objs)
        service = ItemService(repo, (hook,))

        await service.create_multi(session, [ItemCreate(name=o.name) for o in objs])

        rows = _rows(outbox_repo)
        assert len(rows) == len(objs), f"expected one outbox row per object, got {len(rows)}"
        assert [r.aggregate_id for r in rows] == [str(o.id) for o in objs]
        assert {r.event_type for r in rows} == {"ITEM_CREATED"}
        assert [r.payload["name"] for r in rows] == [o.name for o in objs]

    @pytest.mark.parametrize("outbox_first", [True, False], ids=["outbox_first", "outbox_last"])
    async def test_create_multi_writes_every_row_alongside_a_bulk_collapsing_hook(
        self, repo, outbox_repo, hook, session, objs, outbox_first
    ):
        """
        Regression: DomainEventHook.create_post_multi collapses the bulk path into one
        aggregate event. Before the refactor that override switched off the outbox hook's
        per-item create_post entirely, and create_multi silently wrote ZERO outbox rows.

        Each hook now only collapses its OWN work: one aggregate domain event, still N
        outbox rows. Order of declaration must not matter.
        """
        repo.create_multi = AsyncMock(return_value=objs)
        event_hook = AggregateEventHook()
        hooks = (hook, event_hook) if outbox_first else (event_hook, hook)
        service = ItemService(repo, hooks)

        await service.create_multi(session, [ItemCreate(name=o.name) for o in objs])
        await run_after_commit(session)  # DomainEventHook publishes after commit

        rows = _rows(outbox_repo)
        assert len(rows) == len(objs), (
            f"the bulk-collapsing hook suppressed the outbox: {len(rows)} rows, expected {len(objs)}"
        )
        assert [r.aggregate_id for r in rows] == [str(o.id) for o in objs]
        assert {r.event_type for r in rows} == {"ITEM_CREATED"}
        assert event_hook.published == ["Item.created_multi"], (
            "the event hook should still collapse its own work into one aggregate event"
        )
