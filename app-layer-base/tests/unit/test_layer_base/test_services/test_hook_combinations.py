"""
Hook combination contract
=========================

Hooks are only interesting in combination, and every bug this suite exists to
prevent was a *combination* bug: a hook that overrode a bulk method silently
switched off the per-item hooks of every OTHER hook in the service.

The invariant under test:

    No hook can suppress another hook's callbacks.

A hook overriding a ``*_multi`` method replaces only ITS OWN per-item behaviour.
Every other hook still gets its single-item hook applied to every item.

The generic matrix below combines a recording probe with each real hook that
overrides a bulk method, in both declaration orders. The regression tests at the
bottom pin the three combinations that were actually broken.
"""

import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app_layer_base.base.exceptions.basic import ConflictException
from app_layer_base.base.services.base import (
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
)
from app_layer_base.base.services.detail_delete_response_hook import DetailDeleteResponseHook
from app_layer_base.base.services.event_hook import DomainEventHook
from app_layer_base.base.services.exists_check_hook import ExistsCheckHook
from app_layer_base.base.services.hooks import (
    BaseContextKwargs,
    CreateHook,
    DeleteHook,
    GetHook,
    GetMultiHook,
    UpdateHook,
)
from app_layer_base.base.services.nested_resource_hook import (
    NestedResourceContextKwargs,
    NestedResourceHook,
)
from app_layer_base.base.services.unique_constraints_hook import UniqueConstraintHook
from test_layer_base.mock_models import MockModel, MockRepository

PARENT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
EVENT_TYPES = {"CREATE": "created", "UPDATE": "updated", "DELETE": "deleted"}


# =============================================================================
# Test doubles
# =============================================================================


def make_repo() -> AsyncMock:
    """A repo mock that keeps the real pk-normalization helpers."""
    real = MockRepository()
    repo = AsyncMock()
    repo.primary_keys = real.primary_keys
    repo.model = MockModel
    repo.model_name = MockRepository.model_name
    repo.model_repr = real.model_repr
    repo.normalize_pk = real.normalize_pk
    repo.normalize_pk_as_str = real.normalize_pk_as_str
    return repo


@dataclass
class Recorder:
    """What a probe hook saw, per hook method."""

    calls: dict[str, list[Any]] = field(default_factory=dict)

    def record(self, method: str, value: Any) -> None:
        self.calls.setdefault(method, []).append(value)

    def count(self, method: str) -> int:
        return len(self.calls.get(method, []))


class ProbeHook(
    CreateHook[Any, Any],
    UpdateHook[Any, Any],
    DeleteHook[Any],
    GetHook[Any, Any],
    GetMultiHook[Any, Any],
):
    """
    Opts into every operation and overrides NO bulk method, so it relies entirely
    on the executor applying its single-item hooks per item. That is exactly the
    behaviour other hooks used to be able to switch off.
    """

    def __init__(self, recorder: Recorder, name: str = "probe"):
        self.rec = recorder
        self.name = name

    @asynccontextmanager
    async def create_context(self, op, data):
        self.rec.record("create_context", data)
        yield

    def create_prepare_fields(self, op, data, fields):
        self.rec.record("create_prepare_fields", data)
        return fields

    async def create_post(self, op, obj):
        self.rec.record("create_post", obj)
        return obj

    @asynccontextmanager
    async def delete_context(self, op, pk):
        self.rec.record("delete_context", pk)
        yield

    async def delete_post(self, op, pk, result):
        self.rec.record("delete_post", pk)
        return result


class SpyUniqueHook(UniqueConstraintHook[Any, Any]):
    def __init__(self, duplicate: bool):
        self.duplicate = duplicate

    async def constraints(self, op, data):
        yield MockModel.id == None, "Duplicate!"  # noqa: E711


class SpyEventHook(DomainEventHook[Any, Any]):
    """Overrides create_post_multi / delete_post_multi with one aggregate event."""

    def __init__(self):
        self.published: list[str] = []

    async def publish_event(self, topic, payload):
        self.published.append(topic)


class SpyDetailHook(DetailDeleteResponseHook[Any, Any]):
    def represent(self, obj) -> str:
        return f"Item({obj.id})"


# =============================================================================
# Minimal services
# =============================================================================


class CreateSvc(BaseCreateServiceMixin):
    def __init__(self, repo, hooks, context_model=BaseContextKwargs):
        self._repo = repo
        self._context_model = context_model
        self.hooks = hooks

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return self._context_model


class DeleteSvc(BaseDeleteServiceMixin):
    def __init__(self, repo, hooks, context_model=BaseContextKwargs):
        self._repo = repo
        self._context_model = context_model
        self.hooks = hooks

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return self._context_model


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def session():
    return AsyncMock()


@pytest.fixture
def pks():
    return [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]


@pytest.fixture
def objs(pks):
    out = []
    for pk in pks:
        obj = MagicMock()
        obj.id = pk
        obj.parent_id = PARENT_ID
        out.append(obj)
    return out


@pytest.fixture
def create_repo(objs):
    repo = make_repo()
    repo.exists = AsyncMock(return_value=False)
    repo.create = AsyncMock(return_value=objs[0])
    repo.create_multi = AsyncMock(return_value=objs)
    return repo


@pytest.fixture
def delete_repo(objs, pks):
    repo = make_repo()
    repo.get_by_pk = AsyncMock(side_effect=lambda s, pk: next((o for o in objs if o.id == pk), None))
    repo.get_all = AsyncMock(return_value=objs)
    repo.delete_by_pk = AsyncMock(return_value=True)
    repo.delete_by_pk_multi = AsyncMock(return_value=len(pks))
    return repo


@pytest.fixture
def parent_repo():
    repo = make_repo()
    repo.get_by_pk = AsyncMock(return_value=MagicMock())
    return repo


# =============================================================================
# 1. The invariant: a bulk-overriding hook never suppresses another hook
# =============================================================================
#
# Each entry is a real hook that overrides at least one *_multi method. Pairing
# it with a ProbeHook (which overrides none) must not change what the probe sees.


def _bulk_overriding_create_hooks(parent_repo):
    return {
        "nested": NestedResourceHook(parent_repo),  # overrides create_context_multi
        "domain_event": SpyEventHook(),  # overrides create_post_multi
    }


def _bulk_overriding_delete_hooks(parent_repo):
    return {
        "nested": NestedResourceHook(parent_repo),  # overrides delete_context_multi
        "exists_check": ExistsCheckHook(),  # overrides delete_context_multi
        "domain_event": SpyEventHook(),  # overrides delete_post_multi
    }


@pytest.mark.parametrize("other_id", ["nested", "domain_event"])
@pytest.mark.parametrize("probe_first", [True, False], ids=["probe_first", "probe_last"])
async def test_create_multi_bulk_hook_does_not_suppress_other_hooks(
    session, create_repo, parent_repo, objs, other_id, probe_first
):
    """A hook overriding a create bulk method must not disable another hook's per-item hooks."""
    rec = Recorder()
    probe = ProbeHook(rec)
    other = _bulk_overriding_create_hooks(parent_repo)[other_id]

    hooks = (probe, other) if probe_first else (other, probe)
    svc = CreateSvc(create_repo, hooks, context_model=NestedResourceContextKwargs)

    data = [MagicMock(), MagicMock(), MagicMock()]
    await svc.create_multi(session, data, context={"parent_id": PARENT_ID})

    assert rec.count("create_context") == len(data), (
        f"probe.create_context ran {rec.count('create_context')}x, expected {len(data)} — '{other_id}' suppressed it"
    )
    assert rec.count("create_prepare_fields") == len(data)
    assert rec.count("create_post") == len(objs), (
        f"probe.create_post ran {rec.count('create_post')}x, expected {len(objs)} — '{other_id}' suppressed it"
    )


@pytest.mark.parametrize("other_id", ["nested", "exists_check", "domain_event"])
@pytest.mark.parametrize("probe_first", [True, False], ids=["probe_first", "probe_last"])
async def test_delete_multi_bulk_hook_does_not_suppress_other_hooks(
    session, delete_repo, parent_repo, pks, other_id, probe_first
):
    """A hook overriding a delete bulk method must not disable another hook's per-item hooks."""
    rec = Recorder()
    probe = ProbeHook(rec)
    other = _bulk_overriding_delete_hooks(parent_repo)[other_id]

    hooks = (probe, other) if probe_first else (other, probe)
    svc = DeleteSvc(delete_repo, hooks, context_model=NestedResourceContextKwargs)

    await svc.delete_multi(session, pks, context={"parent_id": PARENT_ID})

    assert rec.count("delete_context") == len(pks), (
        f"probe.delete_context ran {rec.count('delete_context')}x, expected {len(pks)} — '{other_id}' suppressed it"
    )
    assert rec.count("delete_post") == len(pks), (
        f"probe.delete_post ran {rec.count('delete_post')}x, expected {len(pks)} — '{other_id}' suppressed it"
    )


async def test_bulk_override_still_collapses_its_own_work(session, create_repo, parent_repo):
    """
    The point of overriding a bulk method is to do the work once instead of N times.
    That optimisation must survive — it just must not leak onto other hooks.
    """
    rec = Recorder()
    svc = CreateSvc(
        create_repo,
        (NestedResourceHook(parent_repo), ProbeHook(rec)),
        context_model=NestedResourceContextKwargs,
    )

    data = [MagicMock(), MagicMock(), MagicMock()]
    await svc.create_multi(session, data, context={"parent_id": PARENT_ID})

    assert parent_repo.get_by_pk.await_count == 1, "nested hook should check the parent once, not per item"
    assert rec.count("create_context") == len(data), "...while the probe still runs per item"


# =============================================================================
# 2. Execution order
# =============================================================================


async def test_contexts_and_posts_run_in_mirrored_order(session, create_repo, objs):
    """Contexts enter in declaration order; posts run in reverse."""
    order: list[str] = []

    class OrderHook(CreateHook[Any, Any]):
        def __init__(self, name):
            self.name = name

        @asynccontextmanager
        async def create_context(self, op, data):
            order.append(f"enter:{self.name}")
            yield
            order.append(f"exit:{self.name}")

        def create_prepare_fields(self, op, data, fields):
            order.append(f"prepare:{self.name}")
            return fields

        async def create_post(self, op, obj):
            order.append(f"post:{self.name}")
            return obj

    svc = CreateSvc(create_repo, (OrderHook("a"), OrderHook("b"), OrderHook("c")))
    await svc.create(session, MagicMock(), context=None)

    assert order == [
        "enter:a",
        "enter:b",
        "enter:c",
        "prepare:a",
        "prepare:b",
        "prepare:c",
        "post:c",
        "post:b",
        "post:a",
        "exit:c",
        "exit:b",
        "exit:a",
    ]


async def test_raising_hook_blocks_repo_call_and_later_hooks(session, create_repo):
    """A hook that raises before yield stops the operation and the hooks after it."""
    rec = Recorder()

    class Boom(CreateHook[Any, Any]):
        @asynccontextmanager
        async def create_context(self, op, data):
            raise ConflictException("nope", status_code=409)
            yield  # pragma: no cover

    svc = CreateSvc(create_repo, (Boom(), ProbeHook(rec)))

    with pytest.raises(ConflictException):
        await svc.create(session, MagicMock(), context=None)

    assert rec.count("create_context") == 0, "hooks after the failing one must not run"
    create_repo.create.assert_not_awaited()


async def test_operation_state_is_per_call(session, delete_repo, pks):
    """Operation.state must not carry over between service calls."""
    seen: list[dict] = []

    class StateHook(DeleteHook[Any]):
        @asynccontextmanager
        async def delete_context(self, op, pk):
            seen.append(op.state)
            op.state["touched"] = pk
            yield

    svc = DeleteSvc(delete_repo, (StateHook(),))
    await svc.delete(session, pks[0], context=None)
    await svc.delete(session, pks[1], context=None)

    assert len(seen) == 2
    assert seen[0] is not seen[1], "each service call must get a fresh Operation.state"


# =============================================================================
# 3. Regressions — the three combinations that were actually broken
# =============================================================================


async def test_unique_check_runs_on_create_multi_alongside_nested_hook(session, create_repo, parent_repo):
    """
    Was: NestedResourceHook.create_context_multi switched off UniqueConstraintHook's
    per-item check, so create_multi silently wrote duplicates.
    """
    create_repo.exists = AsyncMock(return_value=True)  # a duplicate exists

    svc = CreateSvc(
        create_repo,
        (SpyUniqueHook(duplicate=True), NestedResourceHook(parent_repo)),
        context_model=NestedResourceContextKwargs,
    )

    with pytest.raises(ConflictException):
        await svc.create_multi(session, [MagicMock(), MagicMock()], context={"parent_id": PARENT_ID})

    assert create_repo.exists.await_count >= 1, "unique constraint was never checked"
    create_repo.create_multi.assert_not_awaited()


async def test_detail_delete_representation_survives_exists_check_hook(session, delete_repo, pks, objs):
    """
    Was: ExistsCheckHook.delete_context_multi switched off DetailDeleteResponseHook's
    per-item hooks. Each hook now opts in or out of the bulk path for itself:
    ExistsCheckHook checks existence with one IN query, DetailDeleteResponseHook sits
    delete_multi out (MultipleDeleteResponse has nowhere to put a representation), and
    neither decision touches the other. The single delete still gets its representation.
    """
    svc = DeleteSvc(delete_repo, (SpyDetailHook(), ExistsCheckHook()))

    result = await svc.delete(session, pks[0], context=None)
    assert result.representation == f"Item({pks[0]})", "ExistsCheckHook suppressed the representation"

    delete_repo.get_by_pk.reset_mock()
    delete_repo.get_all.reset_mock()

    await svc.delete_multi(session, pks, context=None)
    assert delete_repo.get_all.await_count == 1, "the bulk existence check should be one IN query"
    delete_repo.get_by_pk.assert_not_awaited()


async def test_detail_delete_gives_each_pk_its_own_representation(session, delete_repo, pks, objs):
    """State lives on the Operation keyed by pk, so items cannot share a representation."""
    hook = SpyDetailHook()
    svc = DeleteSvc(delete_repo, (hook,))

    r1 = await svc.delete(session, pks[0], context=None)
    r2 = await svc.delete(session, pks[1], context=None)

    assert r1.representation == f"Item({pks[0]})"
    assert r2.representation == f"Item({pks[1]})"


async def test_delete_representation_does_not_leak_into_a_later_missing_row(session, pks, objs):
    """
    Was: the hook stashed the text on `self`, so a second delete of a MISSING row
    reported the previous row's representation.
    """
    repo = make_repo()
    repo.get_by_pk = AsyncMock(return_value=objs[0])
    repo.delete_by_pk = AsyncMock(return_value=True)

    svc = DeleteSvc(repo, (SpyDetailHook(),))
    first = await svc.delete(session, pks[0], context=None)
    assert first.representation == f"Item({pks[0]})"

    repo.get_by_pk = AsyncMock(return_value=None)  # second target does not exist
    repo.delete_by_pk = AsyncMock(return_value=False)
    second = await svc.delete(session, pks[1], context=None)

    assert second.representation is None, "stale representation leaked from the previous call"


async def test_domain_event_bulk_event_does_not_suppress_per_item_hooks(session, create_repo, objs):
    """
    Was: DomainEventHook.create_post_multi (one aggregate event) switched off every
    other hook's per-item create_post — which silently dropped outbox rows.
    """
    rec = Recorder()
    event_hook = SpyEventHook()
    svc = CreateSvc(create_repo, (ProbeHook(rec), event_hook))

    await svc.create_multi(session, [MagicMock(), MagicMock(), MagicMock()], context=None)

    assert rec.count("create_post") == len(objs), "per-item create_post was suppressed"
    assert event_hook.published == ["MockModel.created_multi"], (
        "the event hook should still collapse its own work into one aggregate event"
    )
