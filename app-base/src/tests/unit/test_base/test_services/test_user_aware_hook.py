"""Unit tests for UserAwareHooksMixin."""

import uuid

import pytest
from app_base.base.services.base import BaseContextKwargs
from app_base.base.services.user_aware_hook import UserAwareHooksMixin, UserContextKwargs

# =============================================================================
# Concrete service for testing
# =============================================================================


class ConcreteUserAwareService(UserAwareHooksMixin):
    def __init__(self, repo):
        self._repo = repo

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return BaseContextKwargs


# =============================================================================
# Tests for _prepare_create_fields
# =============================================================================


class TestUserAwareCreateFields:
    @pytest.fixture
    def service(self, mock_repo):
        return ConcreteUserAwareService(mock_repo)

    def test_prepare_create_fields_injects_created_by_and_updated_by(self, service):
        user_id = uuid.uuid4()
        context: UserContextKwargs = {"user_id": user_id}

        result = service._prepare_create_fields(obj_data=None, context=context)

        assert result["created_by"] == user_id
        assert result["updated_by"] == user_id

    def test_prepare_create_fields_without_user_id_returns_base(self, service):
        context: BaseContextKwargs = {}

        result = service._prepare_create_fields(obj_data=None, context=context)

        assert "created_by" not in result
        assert "updated_by" not in result

    def test_prepare_create_fields_merges_extra_update_fields(self, service):
        user_id = uuid.uuid4()
        context: UserContextKwargs = {"user_id": user_id}

        result = service._prepare_create_fields(obj_data=None, context=context, extra_field="value")

        assert result["extra_field"] == "value"
        assert result["created_by"] == user_id


# =============================================================================
# Tests for _prepare_update_fields
# =============================================================================


class TestUserAwareUpdateFields:
    @pytest.fixture
    def service(self, mock_repo):
        return ConcreteUserAwareService(mock_repo)

    def test_prepare_update_fields_injects_updated_by(self, service):
        user_id = uuid.uuid4()
        context: UserContextKwargs = {"user_id": user_id}

        result = service._prepare_update_fields(obj_data=None, context=context)

        assert result["updated_by"] == user_id
        assert "created_by" not in result

    def test_prepare_update_fields_without_user_id_returns_base(self, service):
        context: BaseContextKwargs = {}

        result = service._prepare_update_fields(obj_data=None, context=context)

        assert "updated_by" not in result

    def test_prepare_update_fields_merges_extra_update_fields(self, service):
        user_id = uuid.uuid4()
        context: UserContextKwargs = {"user_id": user_id}

        result = service._prepare_update_fields(obj_data=None, context=context, status="active")

        assert result["status"] == "active"
        assert result["updated_by"] == user_id
