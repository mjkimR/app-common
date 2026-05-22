"""
Batch validation of chaining & contract for all asynccontextmanager Hook Mixins
================================================================================

Validation items (for every context method of each Hook):
  1. super() chaining  → Verify SpyAllMixin is reached
  2. body execution    → Confirm with-block entry when yield is present
  3. exception propagation → Verify exceptions raised in body propagate outward
  4. pre-hook blocking → Confirm body is not entered when the hook raises

To add a new Hook, simply append a HookCase entry to the HOOK_CASES list.
"""

import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app_base.base.exceptions.basic import BadRequestException, NotFoundException
from app_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from app_base.base.repos.base import BaseRepository
from app_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateHooks,
    BaseDeleteHooks,
    BaseGetHooks,
    BaseGetMultiHooks,
    BaseUpdateHooks,
)
from app_base.base.services.detail_delete_response_hook import DetailDeleteResponseHookMixin
from app_base.base.services.exists_check_hook import ExistsCheckHooksMixin
from app_base.base.services.nested_resource_hook import (
    NestedResourceContextKwargs,
    NestedResourceHooksMixin,
)
from app_base.base.services.unique_constraints_hook import UniqueConstraintHooksMixin
from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from tests.unit.test_base.conftest import MockModel, MockRepository

# =============================================================================
# Child model for Nested tests (requires parent_id column)
# =============================================================================


class MockChildModel(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "all_hooks_chain_mock_child"
    name: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)


class MockChildRepository(BaseRepository[MockChildModel, BaseModel, BaseModel, BaseModel]):
    model = MockChildModel


# =============================================================================
# SpyAllMixin
# - A single Spy that monitors all context methods.
# - When inherited after a HookMixin, self._called reflects whether
#   super() chaining reached this point.
# =============================================================================


class SpyAllMixin(
    BaseCreateHooks,
    BaseUpdateHooks,
    BaseGetHooks,
    BaseGetMultiHooks,
    BaseDeleteHooks,
):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._called: set[str] = set()

    @asynccontextmanager
    async def _context_create(self, session, obj_data, context):
        self._called.add("_context_create")
        async with super()._context_create(session, obj_data, context):
            yield

    @asynccontextmanager
    async def _context_create_multi(self, session, obj_data_list, context):
        self._called.add("_context_create_multi")
        async with super()._context_create_multi(session, obj_data_list, context):
            yield

    @asynccontextmanager
    async def _context_update(self, session, obj_pk, obj_data, context, partial=True):
        self._called.add("_context_update")
        async with super()._context_update(session, obj_pk, obj_data, context, partial=partial):
            yield

    @asynccontextmanager
    async def _context_delete(self, session, obj_pk, context):
        self._called.add("_context_delete")
        async with super()._context_delete(session, obj_pk, context):
            yield

    @asynccontextmanager
    async def _context_delete_multi(self, session, obj_pks, context):
        self._called.add("_context_delete_multi")
        async with super()._context_delete_multi(session, obj_pks, context):
            yield

    @asynccontextmanager
    async def _context_get(self, session, obj_pk, context):
        self._called.add("_context_get")
        async with super()._context_get(session, obj_pk, context):
            yield

    @asynccontextmanager
    async def _context_get_multi(self, session, context):
        self._called.add("_context_get_multi")
        async with super()._context_get_multi(session, context):
            yield


# =============================================================================
# Concrete Service per Hook
# MRO: _XxxService → HookMixin → SpyAllMixin → Base...
# If HookMixin calls super(), execution reaches SpyAllMixin.
# =============================================================================


class _ExistsCheckSvc(ExistsCheckHooksMixin, SpyAllMixin):
    def __init__(self, repo, parent_repo=None):
        super().__init__()
        self._repo = repo

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs


class _UniqueConstraintSvc(UniqueConstraintHooksMixin, SpyAllMixin):
    def __init__(self, repo, parent_repo=None):
        super().__init__()
        self._repo = repo

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs

    async def _unique_constraints(self, obj_data, context):
        # Use a real SQLAlchemy expression (MagicMock fails inside and_())
        yield MockModel.id == None, "Duplicate."  # noqa: E711


class _DetailDeleteSvc(DetailDeleteResponseHookMixin, SpyAllMixin):
    def __init__(self, repo, parent_repo=None):
        super().__init__()
        self._repo = repo

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs

    def _parse_delete_represent_text(self, obj) -> str:
        return f"Item({obj})"


class _NestedSvc(NestedResourceHooksMixin, SpyAllMixin):
    def __init__(self, repo, parent_repo):
        super().__init__()
        self._repo = repo
        self._parent_repo = parent_repo

    @property
    def repo(self):
        return self._repo

    @property
    def parent_repo(self):
        return self._parent_repo

    @property
    def context_model(self):
        return NestedResourceContextKwargs


# =============================================================================
# HookCase definition
# =============================================================================

NESTED_PARENT_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
NESTED_CTX: dict = {"parent_id": NESTED_PARENT_ID}
BASE_CTX: dict = {}


@dataclass
class HookCase:
    id: str
    make_service: Callable[..., Any]  # (repo, parent_repo) -> service
    call_cm: Callable  # (service, session, pk, context) -> asynccontextmanager
    spy_method: str  # method name to look up in service._called
    context: dict  # context used for the success scenario

    # Setup callables: (repo, parent_repo, pk) -> None
    ok_setup: Callable[..., None]
    fail_setup: Callable[..., None] | None = None  # None = no body-blocking scenario
    fail_exception: type = NotFoundException

    # Set True when a hook intentionally skips super() (e.g. bulk optimisation)
    skip_chaining: bool = False
    skip_chaining_reason: str = ""


# =============================================================================
# Setup helpers
# =============================================================================


def _exists_ok(repo, parent_repo, pk):
    repo.get_by_pk = AsyncMock(return_value=MagicMock())


def _exists_fail(repo, parent_repo, pk):
    repo.get_by_pk = AsyncMock(return_value=None)


def _exists_multi_ok(repo, parent_repo, pk):
    obj = MagicMock()
    obj.id = pk
    repo.get_all = AsyncMock(return_value=[obj])


def _exists_multi_fail(repo, parent_repo, pk):
    repo.get_all = AsyncMock(return_value=[])


def _unique_ok(repo, parent_repo, pk):
    repo.exists = AsyncMock(return_value=False)


def _unique_fail(repo, parent_repo, pk):
    repo.exists = AsyncMock(return_value=True)


def _detail_ok(repo, parent_repo, pk):
    repo.get_by_pk = AsyncMock(return_value=MagicMock())


def _nested_ok(repo, parent_repo, pk):
    """Parent exists + ownership matches."""
    obj = MagicMock()
    obj.id = pk
    obj.parent_id = NESTED_PARENT_ID
    repo.get_by_pk = AsyncMock(return_value=obj)
    repo.get_all = AsyncMock(return_value=[obj])
    parent_repo.get_by_pk = AsyncMock(return_value=MagicMock())
    parent_repo.normalize_pk_as_str = lambda p: (str(p),)
    parent_repo.model_repr = MagicMock(return_value="Parent(id=...)")


def _nested_parent_fail(repo, parent_repo, pk):
    """Parent does not exist → NotFoundException."""
    parent_repo.get_by_pk = AsyncMock(return_value=None)
    parent_repo.normalize_pk_as_str = lambda p: (str(p),)
    parent_repo.model_repr = MagicMock(return_value="Parent(id=...)")


def _nested_ownership_fail(repo, parent_repo, pk):
    """Object belongs to a different parent → NotFoundException."""
    wrong_obj = MagicMock()
    wrong_obj.id = pk
    wrong_obj.parent_id = uuid.uuid4()  # differs from NESTED_PARENT_ID
    repo.get_by_pk = AsyncMock(return_value=wrong_obj)
    parent_repo.get_by_pk = AsyncMock(return_value=MagicMock())
    parent_repo.normalize_pk_as_str = lambda p: (str(p),)
    parent_repo.model_repr = MagicMock(return_value="Parent(id=...)")


def _nested_multi_ok(repo, parent_repo, pk):
    """delete_multi: bulk ownership check passes."""
    obj = MagicMock()
    obj.id = pk
    obj.parent_id = NESTED_PARENT_ID
    repo.get_all = AsyncMock(return_value=[obj])
    parent_repo.get_by_pk = AsyncMock(return_value=MagicMock())
    parent_repo.normalize_pk_as_str = lambda p: (str(p),)
    parent_repo.model_repr = MagicMock(return_value="Parent(id=...)")


def _nested_multi_fail(repo, parent_repo, pk):
    """delete_multi: bulk ownership check fails."""
    wrong_obj = MagicMock()
    wrong_obj.id = pk
    wrong_obj.parent_id = uuid.uuid4()
    repo.get_all = AsyncMock(return_value=[wrong_obj])
    parent_repo.normalize_pk_as_str = lambda p: (str(p),)
    parent_repo.model_repr = MagicMock(return_value="Parent(id=...)")


# =============================================================================
# HOOK_CASES — add a HookCase entry here when introducing a new Hook
# =============================================================================

HOOK_CASES: list[HookCase] = [
    # ------------------------------------------------------------------
    # ExistsCheckHooksMixin
    # ------------------------------------------------------------------
    HookCase(
        id="exists_check / _context_update",
        make_service=lambda repo, parent_repo: _ExistsCheckSvc(repo),
        call_cm=lambda svc, s, pk, ctx: svc._context_update(s, pk, MagicMock(), ctx),
        spy_method="_context_update",
        context=BASE_CTX,
        ok_setup=_exists_ok,
        fail_setup=_exists_fail,
    ),
    HookCase(
        id="exists_check / _context_delete",
        make_service=lambda repo, parent_repo: _ExistsCheckSvc(repo),
        call_cm=lambda svc, s, pk, ctx: svc._context_delete(s, pk, ctx),
        spy_method="_context_delete",
        context=BASE_CTX,
        ok_setup=_exists_ok,
        fail_setup=_exists_fail,
    ),
    HookCase(
        id="exists_check / _context_delete_multi",
        make_service=lambda repo, parent_repo: _ExistsCheckSvc(repo),
        call_cm=lambda svc, s, pk, ctx: svc._context_delete_multi(s, [pk], ctx),
        spy_method="_context_delete_multi",
        context=BASE_CTX,
        ok_setup=_exists_multi_ok,
        fail_setup=_exists_multi_fail,
    ),
    # ------------------------------------------------------------------
    # UniqueConstraintHooksMixin
    # ------------------------------------------------------------------
    HookCase(
        id="unique_constraint / _context_create",
        make_service=lambda repo, parent_repo: _UniqueConstraintSvc(repo),
        call_cm=lambda svc, s, pk, ctx: svc._context_create(s, MagicMock(), ctx),
        spy_method="_context_create",
        context=BASE_CTX,
        ok_setup=_unique_ok,
        fail_setup=_unique_fail,
        fail_exception=BadRequestException,
    ),
    HookCase(
        id="unique_constraint / _context_update",
        make_service=lambda repo, parent_repo: _UniqueConstraintSvc(repo),
        call_cm=lambda svc, s, pk, ctx: svc._context_update(s, pk, MagicMock(), ctx),
        spy_method="_context_update",
        context=BASE_CTX,
        ok_setup=_unique_ok,
        fail_setup=_unique_fail,
        fail_exception=BadRequestException,
    ),
    # ------------------------------------------------------------------
    # DetailDeleteResponseHookMixin
    # ------------------------------------------------------------------
    HookCase(
        id="detail_delete / _context_delete",
        make_service=lambda repo, parent_repo: _DetailDeleteSvc(repo),
        call_cm=lambda svc, s, pk, ctx: svc._context_delete(s, pk, ctx),
        spy_method="_context_delete",
        context=BASE_CTX,
        ok_setup=_detail_ok,
        fail_setup=None,  # No body-blocking scenario: missing object is silently skipped
    ),
    # ------------------------------------------------------------------
    # NestedResourceHooksMixin
    # ------------------------------------------------------------------
    HookCase(
        id="nested / _context_create",
        make_service=lambda repo, parent_repo: _NestedSvc(repo, parent_repo),
        call_cm=lambda svc, s, pk, ctx: svc._context_create(s, MagicMock(), ctx),
        spy_method="_context_create",
        context=NESTED_CTX,
        ok_setup=_nested_ok,
        fail_setup=_nested_parent_fail,
    ),
    HookCase(
        id="nested / _context_create_multi",
        make_service=lambda repo, parent_repo: _NestedSvc(repo, parent_repo),
        call_cm=lambda svc, s, pk, ctx: svc._context_create_multi(s, [MagicMock()], ctx),
        spy_method="_context_create_multi",
        context=NESTED_CTX,
        ok_setup=_nested_ok,
        fail_setup=_nested_parent_fail,
    ),
    HookCase(
        id="nested / _context_get_multi",
        make_service=lambda repo, parent_repo: _NestedSvc(repo, parent_repo),
        call_cm=lambda svc, s, pk, ctx: svc._context_get_multi(s, ctx),
        spy_method="_context_get_multi",
        context=NESTED_CTX,
        ok_setup=_nested_ok,
        fail_setup=_nested_parent_fail,
    ),
    HookCase(
        id="nested / _context_get",
        make_service=lambda repo, parent_repo: _NestedSvc(repo, parent_repo),
        call_cm=lambda svc, s, pk, ctx: svc._context_get(s, pk, ctx),
        spy_method="_context_get",
        context=NESTED_CTX,
        ok_setup=_nested_ok,
        fail_setup=_nested_ownership_fail,
    ),
    HookCase(
        id="nested / _context_update",
        make_service=lambda repo, parent_repo: _NestedSvc(repo, parent_repo),
        call_cm=lambda svc, s, pk, ctx: svc._context_update(s, pk, MagicMock(), ctx),
        spy_method="_context_update",
        context=NESTED_CTX,
        ok_setup=_nested_ok,
        fail_setup=_nested_ownership_fail,
    ),
    HookCase(
        id="nested / _context_delete",
        make_service=lambda repo, parent_repo: _NestedSvc(repo, parent_repo),
        call_cm=lambda svc, s, pk, ctx: svc._context_delete(s, pk, ctx),
        spy_method="_context_delete",
        context=NESTED_CTX,
        ok_setup=_nested_ok,
        fail_setup=_nested_ownership_fail,
    ),
    HookCase(
        id="nested / _context_delete_multi",
        make_service=lambda repo, parent_repo: _NestedSvc(repo, parent_repo),
        call_cm=lambda svc, s, pk, ctx: svc._context_delete_multi(s, [pk], ctx),
        spy_method="_context_delete_multi",
        context=NESTED_CTX,
        ok_setup=_nested_multi_ok,
        fail_setup=_nested_multi_fail,
    ),
]

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def sample_uuid():
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def mock_session():
    return AsyncMock()


@pytest.fixture
def mock_repo():
    _real = MockRepository()
    repo = AsyncMock()
    repo.primary_keys = _real.primary_keys
    repo.model = MockModel
    repo.model_name = MockRepository.model_name
    repo.model_repr = _real.model_repr
    repo.normalize_pk = _real.normalize_pk
    repo.normalize_pk_as_str = _real.normalize_pk_as_str
    return repo


@pytest.fixture
def mock_parent_repo():
    _real = MockRepository()
    repo = AsyncMock()
    repo.primary_keys = _real.primary_keys
    repo.model = MockModel
    repo.model_name = MockRepository.model_name
    repo.model_repr = _real.model_repr
    repo.normalize_pk = _real.normalize_pk
    repo.normalize_pk_as_str = _real.normalize_pk_as_str
    return repo


# =============================================================================
# Generic test class — same four contracts applied to every entry in HOOK_CASES
# =============================================================================


@pytest.mark.parametrize("case", HOOK_CASES, ids=[c.id for c in HOOK_CASES])
class TestAllHooksChaining:
    """
    Verifies that every Hook Mixin's asynccontextmanager methods honour the contract.

    Tests:
      - test_super_chaining              : super() call reaches SpyAllMixin
      - test_body_executes               : with-block is entered (yield present)
      - test_body_exception_propagates   : exceptions raised in body propagate outward
      - test_pre_hook_blocks_body        : pre-hook exception prevents body execution
    """

    # -------------------------------------------------------------------------
    # 1. super() chaining
    # -------------------------------------------------------------------------

    async def test_super_chaining(self, case, mock_repo, mock_parent_repo, mock_session, sample_uuid):
        """SpyAllMixin must be reached when HookMixin calls super() correctly."""
        if case.skip_chaining:
            pytest.skip(case.skip_chaining_reason)

        case.ok_setup(mock_repo, mock_parent_repo, sample_uuid)
        service = case.make_service(mock_repo, mock_parent_repo)

        async with case.call_cm(service, mock_session, sample_uuid, case.context):
            pass

        assert case.spy_method in service._called, (
            f"{case.id}: SpyAllMixin.{case.spy_method} was not executed → super() chaining may be broken"
        )

    # -------------------------------------------------------------------------
    # 2. body execution (yield present)
    # -------------------------------------------------------------------------

    async def test_body_executes(self, case, mock_repo, mock_parent_repo, mock_session, sample_uuid):
        """Code inside the with-block must actually run (missing yield prevents entry)."""
        case.ok_setup(mock_repo, mock_parent_repo, sample_uuid)
        service = case.make_service(mock_repo, mock_parent_repo)
        body_executed = False

        async with case.call_cm(service, mock_session, sample_uuid, case.context):
            body_executed = True

        assert body_executed, f"{case.id}: with-block body was not executed → possible missing yield"

    # -------------------------------------------------------------------------
    # 3. exception propagation
    # -------------------------------------------------------------------------

    async def test_body_exception_propagates(self, case, mock_repo, mock_parent_repo, mock_session, sample_uuid):
        """Exceptions raised inside the with-block must propagate outward (not be swallowed)."""
        case.ok_setup(mock_repo, mock_parent_repo, sample_uuid)
        service = case.make_service(mock_repo, mock_parent_repo)

        with pytest.raises(RuntimeError, match=r"body error"):
            async with case.call_cm(service, mock_session, sample_uuid, case.context):
                raise RuntimeError("body error")

    # -------------------------------------------------------------------------
    # 4. pre-hook exception blocks body entry
    # -------------------------------------------------------------------------

    async def test_pre_hook_blocks_body(self, case, mock_repo, mock_parent_repo, mock_session, sample_uuid):
        """When a hook raises before yield, the body must not be entered."""
        if case.fail_setup is None:
            pytest.skip(f"{case.id}: no body-blocking scenario for this Hook")

        case.fail_setup(mock_repo, mock_parent_repo, sample_uuid)
        service = case.make_service(mock_repo, mock_parent_repo)
        body_executed = False

        with pytest.raises(case.fail_exception):
            async with case.call_cm(service, mock_session, sample_uuid, case.context):
                body_executed = True  # must not be reached

        assert not body_executed, (
            f"{case.id}: body was executed after a pre-hook exception → check whether yield is placed before the raise"
        )
