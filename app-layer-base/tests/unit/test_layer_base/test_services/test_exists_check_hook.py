"""Unit tests for ExistsCheckHook."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.services.base import BaseContextKwargs, BaseDeleteServiceMixin
from app_layer_base.base.services.exists_check_hook import ExistsCheckHook
from app_layer_base.base.services.hooks import Operation
from test_layer_base.mock_models import MockModel, MockRepository, MockUpdateSchema

# =============================================================================
# Service wiring the hook, for the end-to-end checks
# =============================================================================


class ExistsCheckDeleteService(
    BaseDeleteServiceMixin[MockRepository, MockModel, BaseContextKwargs],
):
    def __init__(self, repo):
        self._repo = repo
        self.hooks = (ExistsCheckHook(),)

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
    return ExistsCheckHook()


@pytest.fixture
def composite_op(mock_async_session, composite_repo_mock) -> Operation:
    return Operation(session=mock_async_session, context={}, repo=composite_repo_mock)


def _existing(repo, pk) -> MagicMock:
    """A row whose pk columns carry `pk` (single value or composite tuple)."""
    obj = MagicMock()
    values = repo.normalize_pk(pk)
    for col, value in zip(repo.primary_keys, values, strict=True):
        setattr(obj, col.key, value)
    return obj


# =============================================================================
# update_context
# =============================================================================


class TestExistsCheckUpdate:
    async def test_passes_when_obj_exists(self, hook, base_op, sample_uuid):
        base_op.repo.get_by_pk = AsyncMock(return_value=MagicMock())

        async with hook.update_context(base_op, sample_uuid, MockUpdateSchema()):
            pass  # No exception expected

    async def test_raises_not_found_when_obj_missing(self, hook, base_op, sample_uuid):
        base_op.repo.get_by_pk = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException) as exc:
            async with hook.update_context(base_op, sample_uuid, MockUpdateSchema()):
                pass

        assert str(sample_uuid) in exc.value.log_message


# =============================================================================
# delete_context
# =============================================================================


class TestExistsCheckDelete:
    async def test_passes_when_obj_exists(self, hook, base_op, sample_uuid):
        base_op.repo.get_by_pk = AsyncMock(return_value=MagicMock())

        async with hook.delete_context(base_op, sample_uuid):
            pass  # No exception expected

    async def test_raises_not_found_when_obj_missing(self, hook, base_op, sample_uuid):
        base_op.repo.get_by_pk = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            async with hook.delete_context(base_op, sample_uuid):
                pass


# =============================================================================
# delete_context_multi -- one IN query instead of one lookup per pk
# =============================================================================


class TestExistsCheckDeleteMulti:
    async def test_passes_when_all_exist(self, hook, base_op, sample_uuid):
        base_op.repo.get_all = AsyncMock(return_value=[_existing(base_op.repo, sample_uuid)])

        async with hook.delete_context_multi(base_op, [sample_uuid]):
            pass  # No exception expected

    async def test_uses_a_single_in_query_for_many_pks(self, hook, base_op):
        pks = [uuid.uuid4() for _ in range(3)]
        base_op.repo.get_all = AsyncMock(return_value=[_existing(base_op.repo, pk) for pk in pks])

        async with hook.delete_context_multi(base_op, pks):
            pass

        base_op.repo.get_all.assert_awaited_once()
        base_op.repo.get_by_pk.assert_not_awaited()
        where = base_op.repo.get_all.await_args.kwargs["where"]
        assert len(where) == 1
        assert "mock_items.id IN" in str(where[0])

    async def test_raises_not_found_listing_only_the_missing_pks(self, hook, base_op, sample_uuid):
        present, missing = sample_uuid, uuid.uuid4()
        base_op.repo.get_all = AsyncMock(return_value=[_existing(base_op.repo, present)])

        with pytest.raises(NotFoundException) as exc:
            async with hook.delete_context_multi(base_op, [present, missing]):
                pass

        assert str(missing) in exc.value.log_message
        assert str(present) not in exc.value.log_message

    async def test_string_pk_matches_a_uuid_row(self, hook, base_op, sample_uuid):
        """Normalization means str vs UUID is not a false miss."""
        base_op.repo.get_all = AsyncMock(return_value=[_existing(base_op.repo, sample_uuid)])

        async with hook.delete_context_multi(base_op, [str(sample_uuid)]):
            pass  # No exception expected

    async def test_skips_the_query_for_an_empty_list(self, hook, base_op):
        async with hook.delete_context_multi(base_op, []):
            pass

        base_op.repo.get_all.assert_not_awaited()

    # --- composite primary key -------------------------------------------------

    async def test_composite_pk_uses_a_tuple_in_query(self, hook, composite_op):
        tenant = uuid.uuid4()
        pks = [(tenant, "A"), (tenant, "B")]
        composite_op.repo.get_all = AsyncMock(return_value=[_existing(composite_op.repo, pk) for pk in pks])

        async with hook.delete_context_multi(composite_op, pks):
            pass

        composite_op.repo.get_all.assert_awaited_once()
        where = composite_op.repo.get_all.await_args.kwargs["where"]
        rendered = str(where[0])
        assert "tenant_id" in rendered
        assert "code" in rendered
        assert "IN" in rendered

    async def test_composite_pk_raises_when_one_is_missing(self, hook, composite_op):
        tenant = uuid.uuid4()
        present, missing = (tenant, "A"), (tenant, "B")
        composite_op.repo.get_all = AsyncMock(return_value=[_existing(composite_op.repo, present)])

        with pytest.raises(NotFoundException) as exc:
            async with hook.delete_context_multi(composite_op, [present, missing]):
                pass

        assert "code=B" in exc.value.log_message
        assert "code=A" not in exc.value.log_message


# =============================================================================
# End-to-end through a service
# =============================================================================


class TestExistsCheckThroughService:
    @pytest.fixture
    def service(self, mock_repo):
        return ExistsCheckDeleteService(mock_repo)

    async def test_delete_of_a_missing_row_never_reaches_the_repo(
        self, service, mock_async_session, mock_repo, sample_uuid
    ):
        mock_repo.get_by_pk = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.delete(mock_async_session, sample_uuid)

        mock_repo.delete_by_pk.assert_not_awaited()

    async def test_delete_of_an_existing_row_goes_through(self, service, mock_async_session, mock_repo, sample_uuid):
        mock_repo.get_by_pk = AsyncMock(return_value=MagicMock())
        mock_repo.delete_by_pk = AsyncMock(return_value=True)

        result = await service.delete(mock_async_session, sample_uuid)

        assert result.success is True
        mock_repo.delete_by_pk.assert_awaited_once()
