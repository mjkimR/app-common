import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app_prebuilt_outbox.hooks import BaseOutboxHook


class ConcreteOutboxHook(BaseOutboxHook):
    """Minimal concrete hook wiring a mock aggregate repo + mock outbox repo."""

    def __init__(self, repo, outbox_repo):
        self._repo = repo
        self._outbox_repo = outbox_repo

    @property
    def repo(self):
        return self._repo

    @property
    def outbox_repo(self):
        return self._outbox_repo

    @property
    def _event_type_dict(self):
        return {"CREATE": "ITEM_CREATED", "UPDATE": "ITEM_UPDATED", "DELETE": "ITEM_DELETED"}

    def _get_outbox_payload(self, obj, context, outbox_identity):
        return {"id": outbox_identity["aggregate_id"], "name": getattr(obj, "name", None)}


@pytest.fixture
def obj_id():
    return uuid.uuid4()


@pytest.fixture
def obj(obj_id):
    o = MagicMock()
    o.id = obj_id
    o.name = "widget"
    return o


@pytest.fixture
def hook():
    repo = MagicMock()
    pk_col = MagicMock()
    pk_col.key = "id"
    repo.primary_keys = [pk_col]
    repo.model_name.return_value = "Item"
    repo.normalize_pk_as_str.side_effect = lambda pk: [str(pk)]

    outbox_repo = MagicMock()
    outbox_repo.create = AsyncMock()

    return ConcreteOutboxHook(repo, outbox_repo)


def _emitted(hook):
    """The OutboxCreate passed to outbox_repo.create."""
    assert hook.outbox_repo.create.await_count == 1
    return hook.outbox_repo.create.await_args.kwargs["obj_in"]


class TestOutboxHook:
    async def test_post_create_emits_created_event(self, hook, obj, obj_id):
        await hook._post_create(MagicMock(), obj, {})

        emitted = _emitted(hook)
        assert emitted.aggregate_type == "Item"
        assert emitted.aggregate_id == str(obj_id)
        assert emitted.event_type == "ITEM_CREATED"
        assert emitted.payload == {"id": str(obj_id), "name": "widget"}

    async def test_post_update_emits_updated_event(self, hook, obj, obj_id):
        await hook._post_update(MagicMock(), obj, {})

        emitted = _emitted(hook)
        assert emitted.event_type == "ITEM_UPDATED"
        assert emitted.aggregate_id == str(obj_id)

    async def test_context_delete_emits_deleted_event(self, hook, obj, obj_id):
        hook.repo.get_by_pk = AsyncMock(return_value=obj)

        async with hook._context_delete(MagicMock(), obj_id, {}):
            pass

        emitted = _emitted(hook)
        assert emitted.event_type == "ITEM_DELETED"
        assert emitted.aggregate_id == str(obj_id)

    async def test_context_delete_skips_when_object_missing(self, hook, obj_id):
        hook.repo.get_by_pk = AsyncMock(return_value=None)

        async with hook._context_delete(MagicMock(), obj_id, {}):
            pass

        hook.outbox_repo.create.assert_not_awaited()
