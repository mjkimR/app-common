"""Unit tests for UniqueConstraintHook."""

import uuid
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock

import pytest
from app_layer_base.base.exceptions.basic import ConflictException
from app_layer_base.base.services.base import BaseContextKwargs, BaseCreateServiceMixin
from app_layer_base.base.services.hooks import Operation
from app_layer_base.base.services.unique_constraints_hook import UniqueConstraintHook
from sqlalchemy.sql.expression import ColumnElement
from test_layer_base.mock_models import (
    MockCompositeModel,
    MockCreateSchema,
    MockModel,
    MockRepository,
    MockUpdateSchema,
)

# =============================================================================
# Concrete hooks for testing
# =============================================================================


class NameUniqueHook(UniqueConstraintHook[MockModel, BaseContextKwargs]):
    """Yields one (condition, message) pair, and only when `name` is set."""

    async def constraints(self, op, data) -> AsyncIterator[tuple[ColumnElement, str]]:
        if getattr(data, "name", None):
            yield MockModel.name == data.name, "Name already exists."


class TwoConstraintHook(UniqueConstraintHook[MockModel, BaseContextKwargs]):
    """Yields two pairs, so the checking order can be observed."""

    async def constraints(self, op, data) -> AsyncIterator[tuple[ColumnElement, str]]:
        yield MockModel.name == data.name, "Name already exists."
        yield MockModel.description == data.description, "Description already exists."


class BareConditionHook(UniqueConstraintHook[MockModel, BaseContextKwargs]):
    """Yields a bare condition rather than a (condition, message) pair."""

    async def constraints(self, op, data) -> AsyncIterator[ColumnElement]:
        yield MockModel.name == data.name


# =============================================================================
# Service wiring the hook, for the end-to-end checks
# =============================================================================


class UniqueCreateService(
    BaseCreateServiceMixin[MockRepository, MockModel, MockCreateSchema, BaseContextKwargs],
):
    def __init__(self, repo):
        self._repo = repo
        self.hooks = (NameUniqueHook(),)

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def hook():
    return NameUniqueHook()


@pytest.fixture
def create_data():
    return MockCreateSchema(name="some_name", description="some_description")


def condition_of(repo) -> str:
    """The rendered SQL of the condition the hook handed to repo.exists."""
    return str(repo.exists.await_args.args[1])


# =============================================================================
# create_context
# =============================================================================


class TestUniqueConstraintCreate:
    async def test_passes_when_no_duplicate(self, hook, base_op, create_data):
        base_op.repo.exists = AsyncMock(return_value=False)

        async with hook.create_context(base_op, create_data):
            pass  # No exception expected

        base_op.repo.exists.assert_awaited_once()

    async def test_raises_conflict_when_duplicate_found(self, hook, base_op, create_data):
        base_op.repo.exists = AsyncMock(return_value=True)

        with pytest.raises(ConflictException, match=r"Name already exists\.") as exc:
            async with hook.create_context(base_op, create_data):
                pass

        assert exc.value.status_code == 409

    async def test_skips_the_query_when_no_constraint_yields(self, hook, base_op):
        base_op.repo.exists = AsyncMock(return_value=False)

        async with hook.create_context(base_op, MockCreateSchema(name="")):
            pass

        base_op.repo.exists.assert_not_awaited()

    async def test_does_not_exclude_any_row_on_create(self, hook, base_op, create_data):
        """Nothing to exclude yet -- the condition must be the bare constraint."""
        base_op.repo.exists = AsyncMock(return_value=False)

        async with hook.create_context(base_op, create_data):
            pass

        rendered = condition_of(base_op.repo)
        assert "mock_items.name =" in rendered
        assert "!=" not in rendered

    async def test_checks_constraints_in_order_and_stops_at_the_first_hit(self, base_op, create_data):
        base_op.repo.exists = AsyncMock(side_effect=[False, True])

        with pytest.raises(ConflictException, match=r"Description already exists\."):
            async with TwoConstraintHook().create_context(base_op, create_data):
                pass

        assert base_op.repo.exists.await_count == 2

    async def test_bare_condition_falls_back_to_the_default_message(self, base_op, create_data):
        base_op.repo.exists = AsyncMock(return_value=True)

        with pytest.raises(ConflictException, match=r"Data already exists\."):
            async with BareConditionHook().create_context(base_op, create_data):
                pass


# =============================================================================
# update_context -- same check, but the row being updated is excluded
# =============================================================================


class TestUniqueConstraintUpdate:
    async def test_passes_when_no_duplicate(self, hook, base_op, sample_uuid, create_data):
        base_op.repo.exists = AsyncMock(return_value=False)

        async with hook.update_context(base_op, sample_uuid, create_data):
            pass

        base_op.repo.exists.assert_awaited_once()

    async def test_raises_conflict_when_duplicate_found(self, hook, base_op, sample_uuid, create_data):
        base_op.repo.exists = AsyncMock(return_value=True)

        with pytest.raises(ConflictException, match=r"Name already exists\."):
            async with hook.update_context(base_op, sample_uuid, create_data):
                pass

    async def test_excludes_the_row_being_updated(self, hook, base_op, sample_uuid, create_data):
        """The record must not be flagged as a duplicate of itself."""
        base_op.repo.exists = AsyncMock(return_value=False)

        async with hook.update_context(base_op, sample_uuid, create_data):
            pass

        rendered = condition_of(base_op.repo)
        assert "mock_items.name =" in rendered
        assert "mock_items.id !=" in rendered
        assert " AND " in rendered

    async def test_skips_the_query_when_no_constraint_yields(self, hook, base_op, sample_uuid):
        base_op.repo.exists = AsyncMock(return_value=False)

        async with hook.update_context(base_op, sample_uuid, MockUpdateSchema(name=None)):
            pass

        base_op.repo.exists.assert_not_awaited()

    async def test_excludes_the_row_being_updated_on_a_composite_primary_key(
        self, composite_repo_mock, mock_async_session, create_data
    ):
        """
        The exclusion is built from the model's real primary key. A model whose key
        is not a single column named `id` must still be able to update itself.
        """

        class CompositeUniqueHook(UniqueConstraintHook[MockCompositeModel, BaseContextKwargs]):
            async def constraints(self, op, data):
                yield MockCompositeModel.name == data.name, "Name already exists."

        composite_repo_mock.exists = AsyncMock(return_value=False)
        op = Operation(session=mock_async_session, context={}, repo=composite_repo_mock)
        pk = (uuid.uuid4(), "ABC")

        async with CompositeUniqueHook().update_context(op, pk, create_data):
            pass

        rendered = condition_of(composite_repo_mock)
        assert "mock_composite_items.name =" in rendered
        assert "mock_composite_items.tenant_id =" in rendered
        assert "mock_composite_items.code =" in rendered
        assert "NOT (" in rendered, "the whole composite key must be negated as one unit"


# =============================================================================
# End-to-end through a service
# =============================================================================


class TestUniqueConstraintThroughService:
    @pytest.fixture
    def service(self, mock_repo):
        return UniqueCreateService(mock_repo)

    async def test_duplicate_blocks_the_repo_write(self, service, mock_async_session, mock_repo, create_data):
        mock_repo.exists = AsyncMock(return_value=True)

        with pytest.raises(ConflictException):
            await service.create(mock_async_session, create_data)

        mock_repo.create.assert_not_awaited()

    async def test_unique_row_is_written(self, service, mock_async_session, mock_repo, create_data):
        mock_repo.exists = AsyncMock(return_value=False)

        await service.create(mock_async_session, create_data)

        mock_repo.create.assert_awaited_once()

    async def test_create_multi_checks_every_item(self, service, mock_async_session, mock_repo):
        """The default bulk context applies the per-item check to each item."""
        mock_repo.exists = AsyncMock(return_value=False)

        await service.create_multi(
            mock_async_session,
            [MockCreateSchema(name="a"), MockCreateSchema(name="b")],
        )

        assert mock_repo.exists.await_count == 2
