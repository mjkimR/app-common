"""Unit tests for DetailDeleteResponseHook."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app_layer_base.base.schemas.delete_resp import DeleteResponse
from app_layer_base.base.services.base import BaseContextKwargs, BaseDeleteServiceMixin
from app_layer_base.base.services.detail_delete_response_hook import DetailDeleteResponseHook
from app_layer_base.base.services.hooks import Operation
from test_layer_base.mock_models import MockModel, MockRepository

# =============================================================================
# Concrete hooks for testing
# =============================================================================


class ItemDetailDeleteHook(DetailDeleteResponseHook[MockModel, BaseContextKwargs]):
    def represent(self, obj) -> str:
        return f"Item({obj.name})"


class RecordingDetailDeleteHook(ItemDetailDeleteHook):
    """Keeps every per-item DeleteResponse the bulk executor hands out."""

    def __init__(self):
        self.per_item: list[DeleteResponse] = []

    async def delete_post(self, op, pk, result):
        result = await super().delete_post(op, pk, result)
        self.per_item.append(result)
        return result


# =============================================================================
# Service wiring the hook, for the end-to-end checks
# =============================================================================


class DetailDeleteService(BaseDeleteServiceMixin[MockRepository, MockModel, BaseContextKwargs]):
    def __init__(self, repo, hook=None):
        self._repo = repo
        self.hooks = (hook or ItemDetailDeleteHook(),)

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
    return ItemDetailDeleteHook()


def _named(name: str) -> MagicMock:
    obj = MagicMock()
    obj.name = name
    return obj


# =============================================================================
# The hook on its own
# =============================================================================


class TestDetailDeleteResponseHook:
    async def test_context_reads_the_row_and_post_puts_it_on_the_response(self, hook, base_op, sample_uuid):
        base_op.repo.get_by_pk = AsyncMock(return_value=_named("Test Item"))

        async with hook.delete_context(base_op, sample_uuid):
            pass
        result = await hook.delete_post(base_op, sample_uuid, DeleteResponse(success=True))

        assert result.representation == "Item(Test Item)"

    async def test_missing_row_leaves_the_representation_unset(self, hook, base_op, sample_uuid):
        base_op.repo.get_by_pk = AsyncMock(return_value=None)

        async with hook.delete_context(base_op, sample_uuid):
            pass
        result = await hook.delete_post(base_op, sample_uuid, DeleteResponse(success=True))

        assert result.representation is None

    async def test_post_without_a_preceding_context_leaves_the_representation_unset(self, hook, base_op, sample_uuid):
        result = await hook.delete_post(base_op, sample_uuid, DeleteResponse(success=True))

        assert result.representation is None

    async def test_text_is_stashed_on_the_operation_keyed_by_pk_not_on_the_hook(self, hook, base_op, sample_uuid):
        base_op.repo.get_by_pk = AsyncMock(return_value=_named("Test Item"))

        async with hook.delete_context(base_op, sample_uuid):
            pass

        assert base_op.state["detail_delete_represent_text"] == {str(sample_uuid): "Item(Test Item)"}
        assert not hasattr(hook, "_delete_represent_text")
        assert vars(hook) == {}

    async def test_one_hook_instance_serves_two_operations_independently(
        self, hook, mock_async_session, mock_repo, sample_uuid
    ):
        """Hooks are shared, so nothing may be remembered between operations."""
        op_a = Operation(session=mock_async_session, context={}, repo=mock_repo)
        op_b = Operation(session=mock_async_session, context={}, repo=mock_repo)
        mock_repo.get_by_pk = AsyncMock(side_effect=[_named("A"), None])

        async with hook.delete_context(op_a, sample_uuid):
            pass
        async with hook.delete_context(op_b, sample_uuid):
            pass

        assert (await hook.delete_post(op_a, sample_uuid, DeleteResponse())).representation == "Item(A)"
        assert (await hook.delete_post(op_b, sample_uuid, DeleteResponse())).representation is None


# =============================================================================
# End-to-end through a service
# =============================================================================


class TestDetailDeleteThroughService:
    @pytest.fixture
    def service(self, mock_repo):
        return DetailDeleteService(mock_repo)

    async def test_delete_puts_the_representation_on_the_response(
        self, service, mock_async_session, mock_repo, sample_uuid
    ):
        mock_repo.get_by_pk = AsyncMock(return_value=_named("Test Item"))
        mock_repo.delete_by_pk = AsyncMock(return_value=True)

        result = await service.delete(mock_async_session, sample_uuid)

        assert result.representation == "Item(Test Item)"
        assert result.identity == sample_uuid

    async def test_a_second_delete_does_not_inherit_the_first_representation(
        self, service, mock_async_session, mock_repo, sample_uuid
    ):
        """
        Regression: the representation used to be stored on the hook/service, so a
        delete of a row that no longer exists reported the previous row's text.
        """
        other_pk = uuid.uuid4()
        mock_repo.get_by_pk = AsyncMock(side_effect=[_named("First"), None])
        mock_repo.delete_by_pk = AsyncMock(return_value=True)

        first = await service.delete(mock_async_session, sample_uuid)
        second = await service.delete(mock_async_session, other_pk)

        assert first.representation == "Item(First)"
        assert second.representation is None

    async def test_two_deletes_each_report_their_own_row(self, service, mock_async_session, mock_repo, sample_uuid):
        other_pk = uuid.uuid4()
        mock_repo.get_by_pk = AsyncMock(side_effect=[_named("First"), _named("Second")])
        mock_repo.delete_by_pk = AsyncMock(return_value=True)

        first = await service.delete(mock_async_session, sample_uuid)
        second = await service.delete(mock_async_session, other_pk)

        assert first.representation == "Item(First)"
        assert second.representation == "Item(Second)"

    async def test_delete_multi_reads_nothing_and_posts_nothing(self, mock_async_session, mock_repo, sample_uuid):
        """
        MultipleDeleteResponse has no per-item representation field, so this hook
        opts out of the bulk path entirely rather than reading every row to render
        text the caller can never see.
        """
        hook = RecordingDetailDeleteHook()
        service = DetailDeleteService(mock_repo, hook)
        mock_repo.delete_by_pk_multi = AsyncMock(return_value=2)

        result = await service.delete_multi(mock_async_session, [sample_uuid, uuid.uuid4()])

        assert result.deleted_count == 2
        assert hook.per_item == []
        mock_repo.get_by_pk.assert_not_awaited(), "no row should be read for output nobody can see"
