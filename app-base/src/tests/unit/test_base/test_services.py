"""Unit app_tests for app_base.base.services.base module."""

import uuid
from typing import TypedDict
from unittest.mock import AsyncMock, MagicMock

import pytest

from app_base.base.schemas.paginated import PaginatedList
from app_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseServiceMixinInterface,
    BaseUpdateServiceMixin,
)

# =============================================================================
# Custom Context Types for Testing
# =============================================================================


class CustomContextKwargs(TypedDict):
    """Custom context with required field for testing."""

    user_id: uuid.UUID


class OptionalContextKwargs(TypedDict, total=False):
    """Context with optional fields."""

    tenant_id: str
    is_admin: bool


# =============================================================================
# Tests for _ensure_context
# =============================================================================


class TestEnsureContext:
    """Tests for the _ensure_context helper function."""

    def test_ensure_context_with_none_returns_empty_dict(self):
        """Should return empty dict when context is None."""
        result = BaseServiceMixinInterface._ensure_context(None)
        assert result == {}

    def test_ensure_context_with_valid_context_returns_same(self):
        """Should return the same context when valid."""
        # BaseContextKwargs is empty TypedDict, so only empty dict is valid
        context: BaseContextKwargs = {}
        result = BaseServiceMixinInterface._ensure_context(context)
        assert result == context

    def test_ensure_context_with_optional_typed_dict(self):
        """Should pass through valid context for TypedDict with optional fields."""
        context: OptionalContextKwargs = {"tenant_id": "abc"}
        result = BaseServiceMixinInterface._ensure_context(context, OptionalContextKwargs)
        assert result["tenant_id"] == "abc"

    def test_ensure_context_with_empty_dict_returns_empty_dict(self):
        """Should return empty dict when passed empty dict."""
        result = BaseServiceMixinInterface._ensure_context({})
        assert result == {}

    def test_ensure_context_validates_against_typed_dict(self):
        """Should validate context against TypedDict structure."""
        user_id = uuid.uuid4()
        context: CustomContextKwargs = {"user_id": user_id}
        result = BaseServiceMixinInterface._ensure_context(context, CustomContextKwargs)
        assert result["user_id"] == user_id

    def test_ensure_context_with_invalid_type_raises_error(self):
        """Should raise ValueError when context doesn't match TypedDict."""
        # Missing required field user_id
        with pytest.raises(ValueError, match="Invalid context provided"):
            BaseServiceMixinInterface._ensure_context({}, CustomContextKwargs)

    def test_ensure_context_with_optional_fields(self):
        """Should handle TypedDict with optional fields."""
        result = BaseServiceMixinInterface._ensure_context(None, OptionalContextKwargs)
        assert result == {}
        context: OptionalContextKwargs = {"tenant_id": "abc"}

        result_with_values = BaseServiceMixinInterface._ensure_context(context, OptionalContextKwargs)
        assert result_with_values["tenant_id"] == "abc"


# =============================================================================
# Tests for BaseCreateServiceMixin
# =============================================================================


class TestBaseCreateServiceMixin:
    """Tests for create service mixin."""

    @pytest.fixture
    def create_service(self):
        """Create a service with mocked repository."""

        class TestCreateService(BaseCreateServiceMixin):
            def __init__(self):
                self._repo = AsyncMock()

            @property
            def repo(self):
                return self._repo

            @property
            def context_model(self):
                return BaseContextKwargs

        return TestCreateService()

    @pytest.mark.asyncio
    async def test_create_calls_repo_create(self, create_service, mock_async_session, mock_create_schema, mock_model):
        """Should call repository create method."""
        create_service.repo.create.return_value = mock_model

        result = await create_service.create(mock_async_session, mock_create_schema)

        assert result == mock_model
        create_service.repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_with_context(self, create_service, mock_async_session, mock_create_schema, mock_model):
        """Should pass context through create flow."""
        create_service.repo.create.return_value = mock_model

        result = await create_service.create(mock_async_session, mock_create_schema, context={})

        assert result == mock_model

    @pytest.mark.asyncio
    async def test_create_with_prepare_fields_hook(self, mock_async_session, mock_create_schema, mock_model):
        """Should call _prepare_create_fields hook."""

        class TestService(BaseCreateServiceMixin):
            def __init__(self):
                self._repo = AsyncMock()
                self.repo.create.return_value = mock_model

            @property
            def repo(self):
                return self._repo

            @property
            def context_model(self):
                return BaseContextKwargs

            def _prepare_create_fields(self, obj_data, context):
                return {"extra_field": "extra_value"}

        service = TestService()
        await service.create(mock_async_session, mock_create_schema)

        # Verify extra fields were passed to repo.create
        call_kwargs = service.repo.create.call_args
        assert "extra_field" in call_kwargs.kwargs


# =============================================================================
# Tests for BaseUpdateServiceMixin
# =============================================================================


class TestBaseUpdateServiceMixin:
    """Tests for update service mixin."""

    @pytest.fixture
    def update_service(self):
        """Create a service with mocked repository."""

        class TestUpdateService(BaseUpdateServiceMixin):
            def __init__(self):
                self._repo = AsyncMock()

            @property
            def repo(self):
                return self._repo

            @property
            def context_model(self):
                return BaseContextKwargs

        return TestUpdateService()

    @pytest.mark.asyncio
    async def test_update_calls_repo_update(
        self,
        update_service,
        mock_async_session,
        mock_update_schema,
        mock_model,
        sample_uuid,
    ):
        """Should call repository update_by_pk method."""
        update_service.repo.update_by_pk.return_value = mock_model

        result = await update_service.update(mock_async_session, sample_uuid, mock_update_schema)

        assert result == mock_model
        update_service.repo.update_by_pk.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_with_prepare_fields_hook(
        self, mock_async_session, mock_update_schema, mock_model, sample_uuid
    ):
        """Should call _prepare_update_fields hook."""

        class TestService(BaseUpdateServiceMixin):
            def __init__(self):
                self._repo = AsyncMock()
                self.repo.update_by_pk.return_value = mock_model

            @property
            def repo(self):
                return self._repo

            @property
            def context_model(self):
                return BaseContextKwargs

            def _prepare_update_fields(self, obj_data, context):
                return {"updated_by": uuid.uuid4()}

        service = TestService()
        await service.update(mock_async_session, sample_uuid, mock_update_schema)

        call_kwargs = service.repo.update_by_pk.call_args
        assert "updated_by" in call_kwargs.kwargs


# =============================================================================
# Tests for BaseDeleteServiceMixin
# =============================================================================


class TestBaseDeleteServiceMixin:
    """Tests for delete service mixin."""

    @pytest.fixture
    def delete_service(self):
        """Create a service with mocked repository."""

        class TestDeleteService(BaseDeleteServiceMixin):
            def __init__(self):
                self._repo = AsyncMock()

            @property
            def repo(self):
                return self._repo

            @property
            def context_model(self):
                return BaseContextKwargs

        return TestDeleteService()

    @pytest.mark.asyncio
    async def test_delete_calls_repo_delete(self, delete_service, mock_async_session, sample_uuid):
        """Should call repository delete_by_pk method."""
        delete_service.repo.delete_by_pk.return_value = True

        result = await delete_service.delete(mock_async_session, sample_uuid)

        assert result.success is True
        delete_service.repo.delete_by_pk.assert_called_once_with(mock_async_session, pk=sample_uuid)

    @pytest.mark.asyncio
    async def test_delete_returns_false_when_not_found(self, delete_service, mock_async_session, sample_uuid):
        """Should return False when record not found."""
        delete_service.repo.delete_by_pk.return_value = False

        result = await delete_service.delete(mock_async_session, sample_uuid)

        assert result.success is False


# =============================================================================
# Tests for BaseGetServiceMixin
# =============================================================================


class TestBaseGetServiceMixin:
    """Tests for get service mixin."""

    @pytest.fixture
    def get_service(self):
        """Create a service with mocked repository."""

        class TestGetService(BaseGetServiceMixin):
            def __init__(self):
                self._repo = AsyncMock()

            @property
            def repo(self):
                return self._repo

            @property
            def context_model(self):
                return BaseContextKwargs

        return TestGetService()

    @pytest.mark.asyncio
    async def test_get_calls_repo_get_by_pk(self, get_service, mock_async_session, mock_model, sample_uuid):
        """Should call repository get_by_pk method."""
        get_service.repo.get_by_pk.return_value = mock_model

        result = await get_service.get(mock_async_session, sample_uuid)

        assert result == mock_model
        get_service.repo.get_by_pk.assert_called_once_with(mock_async_session, pk=sample_uuid)

    @pytest.mark.asyncio
    async def test_get_returns_none_when_not_found(self, get_service, mock_async_session, sample_uuid):
        """Should return None when record not found."""
        get_service.repo.get_by_pk.return_value = None

        result = await get_service.get(mock_async_session, sample_uuid)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_with_post_get_hook(self, mock_async_session, mock_model, sample_uuid):
        """Should call _post_get hook."""

        class TestService(BaseGetServiceMixin):
            def __init__(self):
                self._repo = AsyncMock()
                self.repo.get_by_pk.return_value = mock_model

            @property
            def repo(self):
                return self._repo

            @property
            def context_model(self):
                return BaseContextKwargs

            async def _post_get(self, session, obj, context):
                if obj:
                    obj.name = "Modified by hook"
                return obj

        service = TestService()
        result = await service.get(mock_async_session, sample_uuid)
        assert result is not None
        assert result.name == "Modified by hook"


# =============================================================================
# Tests for BaseGetMultiServiceMixin
# =============================================================================


class TestBaseGetMultiServiceMixin:
    """Tests for get multi service mixin."""

    @pytest.fixture
    def get_multi_service(self):
        """Create a service with mocked repository."""

        class TestGetMultiService(BaseGetMultiServiceMixin):
            def __init__(self):
                self._repo = AsyncMock()

            @property
            def repo(self):
                return self._repo

            @property
            def context_model(self):
                return BaseContextKwargs

        return TestGetMultiService()

    @pytest.mark.asyncio
    async def test_get_multi_calls_repo_get_multi(self, get_multi_service, mock_async_session, mock_model):
        """Should call repository get_multi method."""
        paginated = PaginatedList(items=[mock_model], total_count=1, offset=0, limit=10)
        get_multi_service.repo.get_multi.return_value = paginated

        result = await get_multi_service.get_multi(mock_async_session, offset=0, limit=10)

        assert result == paginated
        get_multi_service.repo.get_multi.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_multi_with_where_conditions(self, get_multi_service, mock_async_session, mock_model):
        """Should pass where conditions to repository."""
        paginated = PaginatedList(items=[mock_model], total_count=1, offset=0, limit=10)
        get_multi_service.repo.get_multi.return_value = paginated

        where_conditions = [MagicMock()]
        await get_multi_service.get_multi(mock_async_session, where=where_conditions)

        call_kwargs = get_multi_service.repo.get_multi.call_args.kwargs
        assert "where" in call_kwargs

    @pytest.mark.asyncio
    async def test_get_multi_merges_extra_filters(self, mock_async_session, mock_model):
        """Should merge extra filters from _prepare_get_multi_filters hook."""

        class TestService(BaseGetMultiServiceMixin):
            def __init__(self):
                self._repo = AsyncMock()
                paginated = PaginatedList(items=[mock_model], total_count=1, offset=0, limit=10)
                self.repo.get_multi.return_value = paginated

            @property
            def repo(self):
                return self._repo

            @property
            def context_model(self):
                return BaseContextKwargs

            def _prepare_get_multi_filters(self, context):
                return [MagicMock(name="extra_filter")]

        service = TestService()
        await service.get_multi(mock_async_session)

        call_kwargs = service.repo.get_multi.call_args.kwargs
        assert len(call_kwargs["where"]) == 1

    @pytest.mark.asyncio
    async def test_get_multi_merges_where_list_with_extra_filters(self, mock_async_session, mock_model):
        """Should merge where list with extra filters."""

        class TestService(BaseGetMultiServiceMixin):
            def __init__(self):
                self._repo = AsyncMock()
                paginated = PaginatedList(items=[mock_model], total_count=1, offset=0, limit=10)
                self.repo.get_multi.return_value = paginated

            @property
            def repo(self):
                return self._repo

            @property
            def context_model(self):
                return BaseContextKwargs

            def _prepare_get_multi_filters(self, context):
                return [MagicMock(name="extra_filter")]

        service = TestService()
        where_conditions = [MagicMock(name="user_filter")]
        await service.get_multi(mock_async_session, where=where_conditions)

        call_kwargs = service.repo.get_multi.call_args.kwargs
        # Should have both original and extra filters
        assert len(call_kwargs["where"]) == 2
