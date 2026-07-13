"""Unit tests for UserAwareHook."""

import uuid

import pytest
from app_layer_base.base.services.base import BaseCreateServiceMixin, BaseUpdateServiceMixin
from app_layer_base.base.services.hooks import Operation
from app_layer_base.base.services.user_aware_hook import UserAwareHook, UserContextKwargs
from test_layer_base.mock_models import (
    MockCreateSchema,
    MockModel,
    MockRepository,
    MockUpdateSchema,
)

# =============================================================================
# Service wiring the hook, for the end-to-end checks
# =============================================================================


class UserAwareService(
    BaseCreateServiceMixin[MockRepository, MockModel, MockCreateSchema, UserContextKwargs],
    BaseUpdateServiceMixin[MockRepository, MockModel, MockUpdateSchema, MockUpdateSchema, UserContextKwargs],
):
    def __init__(self, repo):
        self._repo = repo
        self.hooks = (UserAwareHook(),)

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return UserContextKwargs


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def hook():
    return UserAwareHook()


@pytest.fixture
def user_id():
    return uuid.uuid4()


@pytest.fixture
def op(mock_async_session, mock_repo, user_id) -> Operation:
    return Operation(session=mock_async_session, context={"user_id": user_id}, repo=mock_repo)


@pytest.fixture
def anon_op(mock_async_session, mock_repo) -> Operation:
    """An Operation whose context carries no user_id."""
    return Operation(session=mock_async_session, context={}, repo=mock_repo)


# =============================================================================
# create_prepare_fields
# =============================================================================


class TestUserAwareCreateFields:
    def test_injects_created_by_and_updated_by(self, hook, op, user_id):
        result = hook.create_prepare_fields(op, MockCreateSchema(name="x"), {})

        assert result["created_by"] == user_id
        assert result["updated_by"] == user_id

    def test_without_user_id_returns_fields_unchanged(self, hook, anon_op):
        result = hook.create_prepare_fields(anon_op, MockCreateSchema(name="x"), {})

        assert "created_by" not in result
        assert "updated_by" not in result

    def test_merges_incoming_extra_fields(self, hook, op, user_id):
        result = hook.create_prepare_fields(op, MockCreateSchema(name="x"), {"extra_field": "value"})

        assert result["extra_field"] == "value"
        assert result["created_by"] == user_id

    def test_does_not_mutate_the_incoming_fields_dict(self, hook, op):
        fields: dict = {}

        hook.create_prepare_fields(op, MockCreateSchema(name="x"), fields)

        assert fields == {}


# =============================================================================
# update_prepare_fields
# =============================================================================


class TestUserAwareUpdateFields:
    def test_injects_updated_by_only(self, hook, op, user_id):
        result = hook.update_prepare_fields(op, MockUpdateSchema(name="x"), {})

        assert result["updated_by"] == user_id
        assert "created_by" not in result

    def test_without_user_id_returns_fields_unchanged(self, hook, anon_op):
        result = hook.update_prepare_fields(anon_op, MockUpdateSchema(name="x"), {})

        assert "updated_by" not in result

    def test_merges_incoming_extra_fields(self, hook, op, user_id):
        result = hook.update_prepare_fields(op, MockUpdateSchema(name="x"), {"status": "active"})

        assert result["status"] == "active"
        assert result["updated_by"] == user_id

    def test_does_not_mutate_the_incoming_fields_dict(self, hook, op):
        fields: dict = {}

        hook.update_prepare_fields(op, MockUpdateSchema(name="x"), fields)

        assert fields == {}


# =============================================================================
# End-to-end through a service
# =============================================================================


class TestUserAwareThroughService:
    @pytest.fixture
    def service(self, mock_repo):
        return UserAwareService(mock_repo)

    async def test_create_stamps_both_columns_on_the_repo_call(self, service, mock_async_session, mock_repo, user_id):
        await service.create(mock_async_session, MockCreateSchema(name="x"), context={"user_id": user_id})

        kwargs = mock_repo.create.await_args.kwargs
        assert kwargs["created_by"] == user_id
        assert kwargs["updated_by"] == user_id

    async def test_patch_stamps_only_updated_by_on_the_repo_call(
        self, service, mock_async_session, mock_repo, sample_uuid, user_id
    ):
        await service.patch(mock_async_session, sample_uuid, MockUpdateSchema(name="x"), context={"user_id": user_id})

        kwargs = mock_repo.update_by_pk.await_args.kwargs
        assert kwargs["updated_by"] == user_id
        assert "created_by" not in kwargs

    async def test_caller_supplied_update_fields_survive(self, service, mock_async_session, mock_repo, user_id):
        await service.create(
            mock_async_session,
            MockCreateSchema(name="x"),
            context={"user_id": user_id},
            tenant="acme",
        )

        kwargs = mock_repo.create.await_args.kwargs
        assert kwargs["tenant"] == "acme"
        assert kwargs["created_by"] == user_id
