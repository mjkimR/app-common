"""Unit tests for NestedResourceHook."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app_layer_base.base.exceptions.basic import NotFoundException
from app_layer_base.base.services.base import BaseCreateServiceMixin, BaseDeleteServiceMixin
from app_layer_base.base.services.hooks import Operation
from app_layer_base.base.services.nested_resource_hook import (
    NestedResourceContextKwargs,
    NestedResourceHook,
)
from test_layer_base.mock_models import MockChildModel, MockChildRepository, MockCreateSchema

# =============================================================================
# Service wiring the hook, for the end-to-end checks
# =============================================================================


class NestedService(
    BaseCreateServiceMixin[MockChildRepository, MockChildModel, MockCreateSchema, NestedResourceContextKwargs],
    BaseDeleteServiceMixin[MockChildRepository, MockChildModel, NestedResourceContextKwargs],
):
    def __init__(self, repo, parent_repo):
        self._repo = repo
        self.hooks = (NestedResourceHook(parent_repo, fk_name="parent_id"),)

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return NestedResourceContextKwargs


# =============================================================================
# Fixtures / helpers
# =============================================================================


@pytest.fixture
def parent_id():
    return uuid.uuid4()


@pytest.fixture
def parent_repo_mock(mock_repo):
    """The parent is a plain MockModel repo (single UUID pk)."""
    return mock_repo


@pytest.fixture
def hook(parent_repo_mock):
    return NestedResourceHook(parent_repo_mock, fk_name="parent_id")


@pytest.fixture
def op(mock_async_session, child_repo_mock, parent_id) -> Operation:
    """Operation over the child repo, scoped to `parent_id`."""
    return Operation(session=mock_async_session, context={"parent_id": parent_id}, repo=child_repo_mock)


def _child(parent_id=None, **attrs) -> MagicMock:
    obj = MagicMock()
    obj.parent_id = parent_id
    for key, value in attrs.items():
        setattr(obj, key, value)
    return obj


# =============================================================================
# Parent existence
# =============================================================================


class TestParentExistence:
    async def test_create_passes_when_the_parent_exists(self, hook, op, parent_repo_mock):
        parent_repo_mock.get_by_pk = AsyncMock(return_value=MagicMock())

        async with hook.create_context(op, MockCreateSchema(name="x")):
            pass

        parent_repo_mock.get_by_pk.assert_awaited_once()

    async def test_create_raises_when_the_parent_is_missing(self, hook, op, parent_repo_mock):
        parent_repo_mock.get_by_pk = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException, match=r"Not Found") as exc:
            async with hook.create_context(op, MockCreateSchema(name="x")):
                pass

        assert "Parent MockModel(" in exc.value.log_message

    async def test_create_multi_checks_the_parent_exactly_once(self, hook, op, parent_repo_mock):
        parent_repo_mock.get_by_pk = AsyncMock(return_value=MagicMock())

        async with hook.create_context_multi(
            op, [MockCreateSchema(name="a"), MockCreateSchema(name="b"), MockCreateSchema(name="c")]
        ):
            pass

        parent_repo_mock.get_by_pk.assert_awaited_once()

    async def test_get_multi_fails_fast_when_the_parent_is_missing(self, hook, op, parent_repo_mock):
        """A missing parent is a 404, not an empty list."""
        parent_repo_mock.get_by_pk = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            async with hook.get_multi_context(op):
                pass

    async def test_get_multi_passes_when_the_parent_exists(self, hook, op, parent_repo_mock):
        parent_repo_mock.get_by_pk = AsyncMock(return_value=MagicMock())

        async with hook.get_multi_context(op):
            pass

        parent_repo_mock.get_by_pk.assert_awaited_once()


# =============================================================================
# Ownership -- get / update / delete
# =============================================================================


class TestOwnership:
    @pytest.fixture(params=["get", "update", "delete"])
    def enter_context(self, request, hook):
        """The three single-item contexts all enforce ownership the same way."""

        def _enter(op, pk):
            if request.param == "get":
                return hook.get_context(op, pk)
            if request.param == "update":
                return hook.update_context(op, pk, MockCreateSchema(name="x"))
            return hook.delete_context(op, pk)

        return _enter

    async def test_passes_when_the_row_belongs_to_the_parent(self, enter_context, op, sample_uuid, parent_id):
        op.repo.get_by_pk = AsyncMock(return_value=_child(parent_id=parent_id))

        async with enter_context(op, sample_uuid):
            pass  # No exception expected

    async def test_raises_when_the_row_belongs_to_another_parent(self, enter_context, op, sample_uuid):
        op.repo.get_by_pk = AsyncMock(return_value=_child(parent_id=uuid.uuid4()))

        with pytest.raises(NotFoundException) as exc:
            async with enter_context(op, sample_uuid):
                pass

        assert "does not belong to" in exc.value.log_message

    async def test_passes_when_the_row_does_not_exist(self, enter_context, op, sample_uuid):
        """A missing row is ExistsCheckHook's call to make, not this hook's."""
        op.repo.get_by_pk = AsyncMock(return_value=None)

        async with enter_context(op, sample_uuid):
            pass  # No exception expected

    async def test_string_fk_matches_a_uuid_parent(self, hook, op, sample_uuid, parent_id):
        """Ownership compares normalized strings, so str vs UUID is not a mismatch."""
        op.repo.get_by_pk = AsyncMock(return_value=_child(parent_id=str(parent_id)))

        async with hook.get_context(op, sample_uuid):
            pass  # No exception expected


# =============================================================================
# Field injection and list filtering
# =============================================================================


class TestFieldInjectionAndFilters:
    def test_create_injects_the_parent_key(self, hook, op, parent_id):
        result = hook.create_prepare_fields(op, MockCreateSchema(name="x"), {})

        assert result["parent_id"] == parent_id

    def test_create_merges_incoming_extra_fields(self, hook, op, parent_id):
        result = hook.create_prepare_fields(op, MockCreateSchema(name="x"), {"extra": "value"})

        assert result["parent_id"] == parent_id
        assert result["extra"] == "value"

    def test_create_does_not_mutate_the_incoming_fields_dict(self, hook, op):
        fields: dict = {}

        hook.create_prepare_fields(op, MockCreateSchema(name="x"), fields)

        assert fields == {}

    def test_get_multi_filters_by_the_parent_key(self, hook, op, parent_id):
        filters = hook.get_multi_prepare_filters(op)

        assert len(filters) == 1
        assert "mock_child_items.parent_id =" in str(filters[0])


# =============================================================================
# delete_multi -- one IN query instead of one lookup per pk
# =============================================================================


class TestOwnershipDeleteMulti:
    async def test_uses_a_single_in_query(self, hook, op, parent_id):
        pks = [uuid.uuid4(), uuid.uuid4()]
        op.repo.get_all = AsyncMock(return_value=[_child(parent_id=parent_id) for _ in pks])

        async with hook.delete_context_multi(op, pks):
            pass

        op.repo.get_all.assert_awaited_once()
        op.repo.get_by_pk.assert_not_awaited()
        where = op.repo.get_all.await_args.kwargs["where"]
        assert "mock_child_items.id IN" in str(where[0])

    async def test_raises_when_any_row_belongs_to_another_parent(self, hook, op, parent_id):
        pks = [uuid.uuid4(), uuid.uuid4()]
        pk_col = op.repo.primary_keys[0].key
        mine = _child(parent_id=parent_id, **{pk_col: pks[0]})
        theirs = _child(parent_id=uuid.uuid4(), **{pk_col: pks[1]})
        op.repo.get_all = AsyncMock(return_value=[mine, theirs])

        with pytest.raises(NotFoundException) as exc:
            async with hook.delete_context_multi(op, pks):
                pass

        assert str(pks[1]) in exc.value.log_message
        assert "does not belong to" in exc.value.log_message

    async def test_skips_the_query_for_an_empty_list(self, hook, op):
        async with hook.delete_context_multi(op, []):
            pass

        op.repo.get_all.assert_not_awaited()

    async def test_composite_child_pk_uses_a_tuple_in_query(
        self, hook, mock_async_session, composite_repo_mock, parent_id
    ):
        composite_op = Operation(session=mock_async_session, context={"parent_id": parent_id}, repo=composite_repo_mock)
        tenant = uuid.uuid4()
        pks = [(tenant, "A"), (tenant, "B")]
        composite_op.repo.get_all = AsyncMock(
            return_value=[_child(parent_id=parent_id, tenant_id=tenant, code=code) for _, code in pks]
        )

        async with hook.delete_context_multi(composite_op, pks):
            pass

        rendered = str(composite_op.repo.get_all.await_args.kwargs["where"][0])
        assert "tenant_id" in rendered
        assert "code" in rendered
        assert "IN" in rendered

    async def test_composite_child_pk_reports_the_whole_key_of_the_foreign_row(
        self, hook, mock_async_session, composite_repo_mock, parent_id
    ):
        composite_op = Operation(session=mock_async_session, context={"parent_id": parent_id}, repo=composite_repo_mock)
        tenant = uuid.uuid4()
        composite_op.repo.get_all = AsyncMock(return_value=[_child(parent_id=uuid.uuid4(), tenant_id=tenant, code="B")])

        with pytest.raises(NotFoundException) as exc:
            async with hook.delete_context_multi(composite_op, [(tenant, "B")]):
                pass

        assert f"MockCompositeModel(tenant_id={tenant}, code=B)" in exc.value.log_message


# =============================================================================
# Composite parent key
# =============================================================================


class TestCompositeParentKey:
    @pytest.fixture
    def composite_parent_id(self):
        return (uuid.uuid4(), "ACME")

    @pytest.fixture
    def hook(self, composite_repo_mock):
        return NestedResourceHook(composite_repo_mock, fk_name=("parent_tenant_id", "parent_code"))

    @pytest.fixture
    def op(self, mock_async_session, child_repo_mock, composite_parent_id) -> Operation:
        return Operation(
            session=mock_async_session,
            context={"parent_id": composite_parent_id},
            repo=child_repo_mock,
        )

    def test_create_injects_every_key_column(self, hook, op, composite_parent_id):
        result = hook.create_prepare_fields(op, MockCreateSchema(name="x"), {})

        assert result["parent_tenant_id"] == composite_parent_id[0]
        assert result["parent_code"] == "ACME"

    def test_get_multi_filters_on_every_key_column(self, hook, op):
        filters = hook.get_multi_prepare_filters(op)

        assert len(filters) == 2
        rendered = " ".join(str(f) for f in filters)
        assert "mock_child_items.parent_tenant_id =" in rendered
        assert "mock_child_items.parent_code =" in rendered

    async def test_ownership_compares_the_whole_key(self, hook, op, sample_uuid, composite_parent_id):
        tenant, code = composite_parent_id
        op.repo.get_by_pk = AsyncMock(return_value=_child(parent_tenant_id=tenant, parent_code=code))

        async with hook.get_context(op, sample_uuid):
            pass  # No exception expected

    async def test_ownership_rejects_a_row_matching_only_part_of_the_key(
        self, hook, op, sample_uuid, composite_parent_id
    ):
        tenant, _ = composite_parent_id
        op.repo.get_by_pk = AsyncMock(return_value=_child(parent_tenant_id=tenant, parent_code="OTHER"))

        with pytest.raises(NotFoundException):
            async with hook.get_context(op, sample_uuid):
                pass


# =============================================================================
# End-to-end through a service
# =============================================================================


class TestNestedThroughService:
    @pytest.fixture
    def service(self, child_repo_mock, parent_repo_mock):
        return NestedService(child_repo_mock, parent_repo_mock)

    async def test_create_scopes_the_row_to_the_parent(
        self, service, mock_async_session, child_repo_mock, parent_repo_mock, parent_id
    ):
        parent_repo_mock.get_by_pk = AsyncMock(return_value=MagicMock())

        await service.create(mock_async_session, MockCreateSchema(name="x"), context={"parent_id": parent_id})

        assert child_repo_mock.create.await_args.kwargs["parent_id"] == parent_id

    async def test_create_under_a_missing_parent_never_reaches_the_repo(
        self, service, mock_async_session, child_repo_mock, parent_repo_mock, parent_id
    ):
        parent_repo_mock.get_by_pk = AsyncMock(return_value=None)

        with pytest.raises(NotFoundException):
            await service.create(mock_async_session, MockCreateSchema(name="x"), context={"parent_id": parent_id})

        child_repo_mock.create.assert_not_awaited()

    async def test_delete_through_the_wrong_parent_never_reaches_the_repo(
        self, service, mock_async_session, child_repo_mock, parent_id, sample_uuid
    ):
        child_repo_mock.get_by_pk = AsyncMock(return_value=_child(parent_id=uuid.uuid4()))

        with pytest.raises(NotFoundException):
            await service.delete(mock_async_session, sample_uuid, context={"parent_id": parent_id})

        child_repo_mock.delete_by_pk.assert_not_awaited()

    async def test_delete_through_the_right_parent_goes_through(
        self, service, mock_async_session, child_repo_mock, parent_id, sample_uuid
    ):
        child_repo_mock.get_by_pk = AsyncMock(return_value=_child(parent_id=parent_id))
        child_repo_mock.delete_by_pk = AsyncMock(return_value=True)

        result = await service.delete(mock_async_session, sample_uuid, context={"parent_id": parent_id})

        assert result.success is True
