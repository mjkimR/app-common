"""
Unit tests for app_layer_base.base.services.base.

The service mixins no longer chain hooks through the MRO: each service declares one
ordered ``hooks`` tuple and the mixin executes it. These tests cover both the service
semantics (what reaches the repository, what comes back) and the executor guarantees
(ordering, isolation between hooks, per-call state).
"""

import uuid
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager
from typing import Any, NotRequired, TypedDict
from unittest.mock import MagicMock

import pytest
from app_layer_base.base.repos.query_options import ListQueryOptions
from app_layer_base.base.schemas.delete_resp import DeleteResponse, MultipleDeleteResponse
from app_layer_base.base.schemas.paginated import PaginatedList
from app_layer_base.base.services.base import (
    BaseContextKwargs,
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseServiceMixinInterface,
    BaseUpdateServiceMixin,
)
from app_layer_base.base.services.hooks import (
    CreateHook,
    DeleteHook,
    GetHook,
    GetMultiHook,
    Operation,
    UpdateHook,
)
from test_layer_base.mock_models import (
    MockCreateSchema,
    MockModel,
    MockRepository,
    MockUpdateSchema,
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
# Concrete services under test
#
# A service is now just: a repo, an ordered `hooks` tuple, and a context model.
# =============================================================================


class _ServiceStub:
    """Shared plumbing for the concrete services below."""

    def __init__(self, repo, hooks: Sequence[Any] = (), context_model=BaseContextKwargs):
        self._repo = repo
        self.hooks = tuple(hooks)
        self._context_model = context_model

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return self._context_model


class CreateService(
    _ServiceStub,
    BaseCreateServiceMixin[MockRepository, MockModel, MockCreateSchema, BaseContextKwargs],
):
    pass


class UpdateService(
    _ServiceStub,
    BaseUpdateServiceMixin[MockRepository, MockModel, MockUpdateSchema, MockUpdateSchema, BaseContextKwargs],
):
    pass


class DeleteService(
    _ServiceStub,
    BaseDeleteServiceMixin[MockRepository, MockModel, BaseContextKwargs],
):
    pass


class GetService(
    _ServiceStub,
    BaseGetServiceMixin[MockRepository, MockModel, BaseContextKwargs],
):
    pass


class GetMultiService(
    _ServiceStub,
    BaseGetMultiServiceMixin[MockRepository, MockModel, BaseContextKwargs],
):
    pass


class FullService(
    _ServiceStub,
    BaseCreateServiceMixin[MockRepository, MockModel, MockCreateSchema, BaseContextKwargs],
    BaseUpdateServiceMixin[MockRepository, MockModel, MockUpdateSchema, MockUpdateSchema, BaseContextKwargs],
    BaseDeleteServiceMixin[MockRepository, MockModel, BaseContextKwargs],
    BaseGetServiceMixin[MockRepository, MockModel, BaseContextKwargs],
    BaseGetMultiServiceMixin[MockRepository, MockModel, BaseContextKwargs],
):
    """Every operation on one service -- used for hook-selection and state tests."""


# =============================================================================
# Reusable test hooks
# =============================================================================


class RecordingHook(
    CreateHook[MockModel, BaseContextKwargs],
    UpdateHook[MockModel, BaseContextKwargs],
    DeleteHook[BaseContextKwargs],
    GetHook[MockModel, BaseContextKwargs],
    GetMultiHook[MockModel, BaseContextKwargs],
):
    """Appends ``<name>:<event>`` to a shared log for every executor callback."""

    def __init__(self, name: str, log: list[str]):
        self.name = name
        self.log = log

    def _record(self, event: str) -> None:
        self.log.append(f"{self.name}:{event}")

    @asynccontextmanager
    async def _span(self, event: str) -> AsyncGenerator[None]:
        self._record(f"{event}:enter")
        try:
            yield
        finally:
            self._record(f"{event}:exit")

    # -- create ---------------------------------------------------------
    @asynccontextmanager
    async def create_context(self, op, data):
        async with self._span("create_context"):
            yield

    def create_prepare_fields(self, op, data, fields):
        self._record("create_prepare_fields")
        return {**fields, f"{self.name}_field": self.name}

    async def create_post(self, op, obj):
        self._record("create_post")
        return obj

    # -- update ---------------------------------------------------------
    @asynccontextmanager
    async def update_context(self, op, pk, data, partial=True):
        async with self._span("update_context"):
            yield

    def update_prepare_fields(self, op, data, fields, partial=True):
        self._record("update_prepare_fields")
        return {**fields, f"{self.name}_field": self.name}

    async def update_post(self, op, obj, partial=True):
        self._record("update_post")
        return obj

    # -- delete ---------------------------------------------------------
    @asynccontextmanager
    async def delete_context(self, op, pk):
        async with self._span("delete_context"):
            yield

    async def delete_post(self, op, pk, result):
        self._record("delete_post")
        return result

    # -- get ------------------------------------------------------------
    @asynccontextmanager
    async def get_context(self, op, pk):
        async with self._span("get_context"):
            yield

    async def get_post(self, op, obj):
        self._record("get_post")
        return obj

    # -- get_multi ------------------------------------------------------
    @asynccontextmanager
    async def get_multi_context(self, op):
        async with self._span("get_multi_context"):
            yield

    def get_multi_prepare_filters(self, op):
        self._record("get_multi_prepare_filters")
        return [MagicMock(name=f"{self.name}_filter")]

    async def get_multi_post(self, op, result):
        self._record("get_multi_post")
        return result


class BoomError(RuntimeError):
    """Raised by hooks that are meant to abort an operation."""


@pytest.fixture
def hook_log() -> list[str]:
    return []


@pytest.fixture
def paginated(mock_model) -> PaginatedList:
    return PaginatedList(items=[mock_model], total_count=1, offset=0, limit=10)


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
        with pytest.raises(ValueError, match=r"Invalid context provided"):
            BaseServiceMixinInterface._ensure_context({}, CustomContextKwargs)

    def test_ensure_context_with_optional_fields(self):
        """Should handle TypedDict with optional fields."""
        result = BaseServiceMixinInterface._ensure_context(None, OptionalContextKwargs)
        assert result == {}
        context: OptionalContextKwargs = {"tenant_id": "abc"}

        result_with_values = BaseServiceMixinInterface._ensure_context(context, OptionalContextKwargs)
        assert result_with_values["tenant_id"] == "abc"


# =============================================================================
# Tests for the context contract: undeclared keys and hook key declarations
# =============================================================================


class DeclaredTenantContext(BaseContextKwargs):
    """BaseContextKwargs subclass probing the inherited ``extra="forbid"``."""

    tenant_id: NotRequired[str]


class NeedsUserIdHook(CreateHook[MockModel, BaseContextKwargs]):
    required_context_keys = frozenset({"user_id"})


class TestContextContractForbidsUndeclaredKeys:
    """An undeclared context key must fail validation, never be silently dropped."""

    def test_base_context_rejects_any_key(self):
        with pytest.raises(ValueError, match=r"Invalid context provided"):
            BaseServiceMixinInterface._ensure_context({"user_id": uuid.uuid4()})

    def test_subclass_inherits_forbid_for_undeclared_keys(self):
        with pytest.raises(ValueError, match=r"Invalid context provided"):
            BaseServiceMixinInterface._ensure_context({"tenant_id": "abc", "oops": 1}, DeclaredTenantContext)

    def test_declared_keys_still_validate(self):
        result = BaseServiceMixinInterface._ensure_context({"tenant_id": "abc"}, DeclaredTenantContext)
        assert result == {"tenant_id": "abc"}

    async def test_service_rejects_undeclared_context_key(self, mock_repo, mock_async_session, mock_create_schema):
        """The create path surfaces the rejection before any repo call."""
        service = CreateService(mock_repo)

        with pytest.raises(ValueError, match=r"Invalid context provided"):
            await service.create(mock_async_session, mock_create_schema, context={"user_id": uuid.uuid4()})

        mock_repo.create.assert_not_called()


class TestRequiredContextKeys:
    """A hook's required_context_keys must be declared on the service's context model."""

    async def test_undeclared_hook_key_fails_fast(self, mock_repo, mock_async_session, mock_create_schema):
        """A context model missing a hook's keys raises before any repo call."""
        service = CreateService(mock_repo, hooks=(NeedsUserIdHook(),))

        with pytest.raises(TypeError, match=r"user_id.*NeedsUserIdHook"):
            await service.create(mock_async_session, mock_create_schema)

        mock_repo.create.assert_not_called()

    async def test_declared_hook_key_passes(self, mock_repo, mock_async_session, mock_create_schema, mock_model):
        class UserIdContext(BaseContextKwargs):
            user_id: NotRequired[uuid.UUID]

        service = CreateService(mock_repo, hooks=(NeedsUserIdHook(),), context_model=UserIdContext)
        mock_repo.create.return_value = mock_model

        result = await service.create(mock_async_session, mock_create_schema, context={"user_id": uuid.uuid4()})

        assert result is mock_model

    async def test_hooks_without_declared_keys_are_unaffected(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model, hook_log
    ):
        """Hooks that declare no required keys keep working against any model."""
        service = CreateService(mock_repo, hooks=(RecordingHook("a", hook_log),))
        mock_repo.create.return_value = mock_model

        result = await service.create(mock_async_session, mock_create_schema)

        assert result is mock_model


# =============================================================================
# Tests for Operation construction (_new_operation)
# =============================================================================


class TestNewOperation:
    """The Operation a service hands to its hooks."""

    async def test_operation_carries_session_repo_and_validated_context(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model
    ):
        """Hooks receive the session, the service repo and the validated context."""
        seen: list[Operation] = []

        class CaptureHook(CreateHook):
            @asynccontextmanager
            async def create_context(self, op, data):
                seen.append(op)
                yield

        service = CreateService(mock_repo, hooks=(CaptureHook(),))
        mock_repo.create.return_value = mock_model

        await service.create(mock_async_session, mock_create_schema, context={})

        (op,) = seen
        assert op.session is mock_async_session
        assert op.repo is mock_repo
        assert op.context == {}
        assert op.state == {}

    async def test_operation_context_is_validated_against_context_model(
        self, mock_repo, mock_async_session, mock_create_schema
    ):
        """A context that doesn't satisfy the service's context_model is rejected."""
        service = CreateService(mock_repo, context_model=CustomContextKwargs)

        with pytest.raises(ValueError, match=r"Invalid context provided"):
            await service.create(mock_async_session, mock_create_schema, context={})

        mock_repo.create.assert_not_called()

    async def test_operation_context_accepts_valid_custom_context(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model
    ):
        """A context matching the service's context_model reaches the hooks intact."""
        user_id = uuid.uuid4()
        seen: list[Any] = []

        class CaptureHook(CreateHook):
            @asynccontextmanager
            async def create_context(self, op, data):
                seen.append(op.context)
                yield

        service = CreateService(mock_repo, hooks=(CaptureHook(),), context_model=CustomContextKwargs)
        mock_repo.create.return_value = mock_model

        await service.create(mock_async_session, mock_create_schema, context={"user_id": user_id})

        assert seen == [{"user_id": user_id}]


# =============================================================================
# Tests for hook selection
# =============================================================================


class TestHookSelection:
    """One ``hooks`` tuple is split per operation by isinstance."""

    def test_hooks_are_filtered_by_operation(self, mock_repo):
        create_only = CreateHook()
        delete_only = DeleteHook()
        everything = RecordingHook("all", [])

        service = FullService(mock_repo, hooks=(create_only, delete_only, everything))

        assert service.create_hooks == (create_only, everything)
        assert service.delete_hooks == (delete_only, everything)
        assert service.update_hooks == (everything,)
        assert service.get_hooks == (everything,)
        assert service.get_multi_hooks == (everything,)

    def test_default_hooks_is_empty(self, mock_repo):
        service = FullService(mock_repo)

        assert service.hooks == ()
        assert service.create_hooks == ()
        assert service.get_multi_hooks == ()

    def test_hook_selection_preserves_declaration_order(self, mock_repo, hook_log):
        first = RecordingHook("first", hook_log)
        second = RecordingHook("second", hook_log)

        service = FullService(mock_repo, hooks=(first, second))

        assert service.create_hooks == (first, second)
        assert service.delete_hooks == (first, second)


# =============================================================================
# Tests for BaseCreateServiceMixin
# =============================================================================


class TestBaseCreateServiceMixin:
    """Tests for create service mixin."""

    async def test_create_calls_repo_create(self, mock_repo, mock_async_session, mock_create_schema, mock_model):
        """Should call repository create method."""
        service = CreateService(mock_repo)
        mock_repo.create.return_value = mock_model

        result = await service.create(mock_async_session, mock_create_schema)

        assert result == mock_model
        mock_repo.create.assert_called_once_with(mock_async_session, obj_in=mock_create_schema)

    async def test_create_with_context(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model, base_context
    ):
        """Should pass context through create flow."""
        service = CreateService(mock_repo)
        mock_repo.create.return_value = mock_model

        result = await service.create(mock_async_session, mock_create_schema, context=base_context)

        assert result == mock_model

    async def test_create_passes_extra_update_fields_to_repo(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model
    ):
        """Caller-supplied **update_fields reach repo.create even without hooks."""
        service = CreateService(mock_repo)
        mock_repo.create.return_value = mock_model

        await service.create(mock_async_session, mock_create_schema, owner_id="u1")

        assert mock_repo.create.call_args.kwargs["owner_id"] == "u1"

    async def test_create_with_prepare_fields_hook(self, mock_repo, mock_async_session, mock_create_schema, mock_model):
        """create_prepare_fields adds columns to the repo.create call."""

        class ExtraFieldHook(CreateHook):
            def create_prepare_fields(self, op, data, fields):
                return {**fields, "extra_field": "extra_value"}

        service = CreateService(mock_repo, hooks=(ExtraFieldHook(),))
        mock_repo.create.return_value = mock_model

        await service.create(mock_async_session, mock_create_schema)

        assert mock_repo.create.call_args.kwargs["extra_field"] == "extra_value"

    async def test_create_prepare_fields_hook_can_override_caller_fields(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model
    ):
        """Hooks see the caller's **update_fields and may rewrite them."""

        class OverrideHook(CreateHook):
            def create_prepare_fields(self, op, data, fields):
                assert fields == {"owner_id": "caller"}
                return {**fields, "owner_id": "hook"}

        service = CreateService(mock_repo, hooks=(OverrideHook(),))
        mock_repo.create.return_value = mock_model

        await service.create(mock_async_session, mock_create_schema, owner_id="caller")

        assert mock_repo.create.call_args.kwargs["owner_id"] == "hook"

    async def test_create_post_hook_can_replace_returned_object(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model
    ):
        """The object returned by create_post is what the service returns."""
        replacement = MockModel(id=uuid.uuid4(), name="replaced")

        class ReplaceHook(CreateHook):
            async def create_post(self, op, obj):
                return replacement

        service = CreateService(mock_repo, hooks=(ReplaceHook(),))
        mock_repo.create.return_value = mock_model

        result = await service.create(mock_async_session, mock_create_schema)

        assert result is replacement

    async def test_create_multi_calls_repo_with_per_item_extra_fields(self, mock_repo, mock_async_session, mock_model):
        """create_multi builds one extra-fields dict per item."""

        class NameFieldHook(CreateHook):
            def create_prepare_fields(self, op, data, fields):
                return {**fields, "slug": data.name.lower()}

        service = CreateService(mock_repo, hooks=(NameFieldHook(),))
        data_list = [MockCreateSchema(name="A"), MockCreateSchema(name="B")]
        mock_repo.create_multi.return_value = [mock_model, mock_model]

        result = await service.create_multi(mock_async_session, data_list, tenant="t1")

        assert result == [mock_model, mock_model]
        kwargs = mock_repo.create_multi.call_args.kwargs
        assert kwargs["objs_in"] == data_list
        assert kwargs["extra_fields_list"] == [
            {"tenant": "t1", "slug": "a"},
            {"tenant": "t1", "slug": "b"},
        ]

    async def test_create_multi_applies_own_create_context_per_item_by_default(
        self, mock_repo, mock_async_session, mock_model
    ):
        """A hook that only defines create_context gets it applied to every item."""
        seen: list[Any] = []

        class PerItemHook(CreateHook):
            @asynccontextmanager
            async def create_context(self, op, data):
                seen.append(data)
                yield

        service = CreateService(mock_repo, hooks=(PerItemHook(),))
        data_list = [MockCreateSchema(name="A"), MockCreateSchema(name="B")]
        mock_repo.create_multi.return_value = [mock_model, mock_model]

        await service.create_multi(mock_async_session, data_list)

        assert seen == data_list

    async def test_create_multi_bulk_override_replaces_only_its_own_per_item_context(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model
    ):
        """Overriding create_context_multi replaces that hook's own per-item context."""
        calls: list[str] = []

        class BulkHook(CreateHook):
            @asynccontextmanager
            async def create_context(self, op, data):
                calls.append("per_item")
                yield

            @asynccontextmanager
            async def create_context_multi(self, op, data_list):
                calls.append("bulk")
                yield

        service = CreateService(mock_repo, hooks=(BulkHook(),))
        mock_repo.create_multi.return_value = [mock_model]

        await service.create_multi(mock_async_session, [mock_create_schema])

        assert calls == ["bulk"]

    @pytest.mark.parametrize("bulk_first", [True, False])
    async def test_create_multi_bulk_override_does_not_suppress_other_hooks(
        self, mock_repo, mock_async_session, mock_model, bulk_first
    ):
        """
        Regression: one hook's bulk override must not disable another hook's per-item context.

        Under the old cooperative-super() chain, a hook that overrode the bulk context
        without calling super() silently swallowed every later hook's per-item hook.
        """
        bulk_calls: list[str] = []
        per_item_seen: list[Any] = []

        class BulkHook(CreateHook):
            @asynccontextmanager
            async def create_context_multi(self, op, data_list):
                bulk_calls.append("bulk")
                yield

        class PerItemHook(CreateHook):
            @asynccontextmanager
            async def create_context(self, op, data):
                per_item_seen.append(data)
                yield

        hooks = (BulkHook(), PerItemHook()) if bulk_first else (PerItemHook(), BulkHook())
        service = CreateService(mock_repo, hooks=hooks)
        data_list = [MockCreateSchema(name="A"), MockCreateSchema(name="B")]
        mock_repo.create_multi.return_value = [mock_model, mock_model]

        await service.create_multi(mock_async_session, data_list)

        assert bulk_calls == ["bulk"]
        assert per_item_seen == data_list

    async def test_create_multi_applies_own_create_post_per_item_by_default(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model
    ):
        """A hook that only defines create_post gets it applied to every created object."""
        seen: list[Any] = []

        class PostHook(CreateHook):
            async def create_post(self, op, obj):
                seen.append(obj)
                return obj

        service = CreateService(mock_repo, hooks=(PostHook(),))
        mock_repo.create_multi.return_value = [mock_model]

        result = await service.create_multi(mock_async_session, [mock_create_schema])

        assert result == [mock_model]
        assert seen == [mock_model]

    async def test_create_multi_bulk_post_override_replaces_only_its_own_per_item_post(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model
    ):
        """Overriding create_post_multi replaces that hook's own per-item create_post."""
        calls: list[str] = []

        class BulkPostHook(CreateHook):
            async def create_post(self, op, obj):
                calls.append("per_item")
                return obj

            async def create_post_multi(self, op, objs):
                calls.append("bulk")
                return objs

        service = CreateService(mock_repo, hooks=(BulkPostHook(),))
        mock_repo.create_multi.return_value = [mock_model]

        result = await service.create_multi(mock_async_session, [mock_create_schema])

        assert result == [mock_model]
        assert calls == ["bulk"]

    async def test_create_multi_bulk_post_override_does_not_suppress_other_hooks(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model
    ):
        """Regression: a bulk post override must not disable another hook's per-item post."""
        bulk_calls: list[str] = []
        per_item_seen: list[Any] = []

        class BulkPostHook(CreateHook):
            async def create_post_multi(self, op, objs):
                bulk_calls.append("bulk")
                return objs

        class PerItemPostHook(CreateHook):
            async def create_post(self, op, obj):
                per_item_seen.append(obj)
                return obj

        service = CreateService(mock_repo, hooks=(BulkPostHook(), PerItemPostHook()))
        mock_repo.create_multi.return_value = [mock_model]

        await service.create_multi(mock_async_session, [mock_create_schema])

        assert bulk_calls == ["bulk"]
        assert per_item_seen == [mock_model]


# =============================================================================
# Tests for BaseUpdateServiceMixin
# =============================================================================


class TestBaseUpdateServiceMixin:
    """Tests for update service mixin."""

    async def test_put_calls_repo_update_with_partial_false(
        self, mock_repo, mock_async_session, mock_update_schema, mock_model, sample_uuid
    ):
        """Should call repository update_by_pk method with partial=False."""
        service = UpdateService(mock_repo)
        mock_repo.update_by_pk.return_value = mock_model

        result = await service.put(mock_async_session, sample_uuid, mock_update_schema)

        assert result == mock_model
        mock_repo.update_by_pk.assert_called_once_with(
            mock_async_session, pk=sample_uuid, obj_in=mock_update_schema, partial=False
        )

    async def test_patch_calls_repo_update_with_partial_true(
        self, mock_repo, mock_async_session, mock_update_schema, mock_model, sample_uuid
    ):
        """Should call repository update_by_pk method with partial=True."""
        service = UpdateService(mock_repo)
        mock_repo.update_by_pk.return_value = mock_model

        result = await service.patch(mock_async_session, sample_uuid, mock_update_schema)

        assert result == mock_model
        mock_repo.update_by_pk.assert_called_once_with(
            mock_async_session, pk=sample_uuid, obj_in=mock_update_schema, partial=True
        )

    async def test_update_passes_extra_update_fields_to_repo(
        self, mock_repo, mock_async_session, mock_update_schema, mock_model, sample_uuid
    ):
        """Caller-supplied **update_fields reach repo.update_by_pk."""
        service = UpdateService(mock_repo)
        mock_repo.update_by_pk.return_value = mock_model

        await service.patch(mock_async_session, sample_uuid, mock_update_schema, updated_by="admin")

        assert mock_repo.update_by_pk.call_args.kwargs["updated_by"] == "admin"

    async def test_update_prepare_fields_hook_adds_fields(
        self, mock_repo, mock_async_session, mock_update_schema, mock_model, sample_uuid
    ):
        """update_prepare_fields adds columns to the repo.update_by_pk call."""

        class ExtraFieldHook(UpdateHook):
            def update_prepare_fields(self, op, data, fields, partial=True):
                return {**fields, "extra_field": "extra_value"}

        service = UpdateService(mock_repo, hooks=(ExtraFieldHook(),))
        mock_repo.update_by_pk.return_value = mock_model

        await service.put(mock_async_session, sample_uuid, mock_update_schema)

        assert mock_repo.update_by_pk.call_args.kwargs["extra_field"] == "extra_value"

    @pytest.mark.parametrize(("method", "expected_partial"), [("put", False), ("patch", True)])
    async def test_update_hooks_receive_partial_flag_and_pk(
        self,
        mock_repo,
        mock_async_session,
        mock_update_schema,
        mock_model,
        sample_uuid,
        method,
        expected_partial,
    ):
        """Every update hook callback is told whether this is a PUT or a PATCH."""
        seen: dict[str, Any] = {}

        class SpyHook(UpdateHook):
            @asynccontextmanager
            async def update_context(self, op, pk, data, partial=True):
                seen["context"] = (pk, data, partial)
                yield

            def update_prepare_fields(self, op, data, fields, partial=True):
                seen["fields"] = partial
                return fields

            async def update_post(self, op, obj, partial=True):
                seen["post"] = partial
                return obj

        service = UpdateService(mock_repo, hooks=(SpyHook(),))
        mock_repo.update_by_pk.return_value = mock_model

        await getattr(service, method)(mock_async_session, sample_uuid, mock_update_schema)

        assert seen["context"] == (sample_uuid, mock_update_schema, expected_partial)
        assert seen["fields"] is expected_partial
        assert seen["post"] is expected_partial

    async def test_update_post_receives_none_when_row_missing(
        self, mock_repo, mock_async_session, mock_update_schema, sample_uuid
    ):
        """update_post sees None (and the service returns None) when the row doesn't exist."""
        seen: list[Any] = []

        class SpyHook(UpdateHook):
            async def update_post(self, op, obj, partial=True):
                seen.append(obj)
                return obj

        service = UpdateService(mock_repo, hooks=(SpyHook(),))
        mock_repo.update_by_pk.return_value = None

        result = await service.patch(mock_async_session, sample_uuid, mock_update_schema)

        assert result is None
        assert seen == [None]

    async def test_update_post_can_replace_returned_object(
        self, mock_repo, mock_async_session, mock_update_schema, mock_model, sample_uuid
    ):
        """The object returned by update_post is what the service returns."""
        replacement = MockModel(id=uuid.uuid4(), name="replaced")

        class ReplaceHook(UpdateHook):
            async def update_post(self, op, obj, partial=True):
                return replacement

        service = UpdateService(mock_repo, hooks=(ReplaceHook(),))
        mock_repo.update_by_pk.return_value = mock_model

        result = await service.put(mock_async_session, sample_uuid, mock_update_schema)

        assert result is replacement


# =============================================================================
# Tests for BaseDeleteServiceMixin
# =============================================================================


class TestBaseDeleteServiceMixin:
    """Tests for delete service mixin."""

    async def test_delete_calls_repo_delete(self, mock_repo, mock_async_session, sample_uuid):
        """Should call repository delete_by_pk method."""
        service = DeleteService(mock_repo)
        mock_repo.delete_by_pk.return_value = True

        result = await service.delete(mock_async_session, sample_uuid)

        assert result.success is True
        assert result.identity == sample_uuid
        mock_repo.delete_by_pk.assert_called_once_with(mock_async_session, pk=sample_uuid)

    async def test_delete_returns_false_when_not_found(self, mock_repo, mock_async_session, sample_uuid):
        """Should return False when record not found."""
        service = DeleteService(mock_repo)
        mock_repo.delete_by_pk.return_value = False

        result = await service.delete(mock_async_session, sample_uuid)

        assert result.success is False

    async def test_delete_post_hook_can_enrich_response(self, mock_repo, mock_async_session, sample_uuid):
        """delete_post receives the pk plus the DeleteResponse and may replace it."""
        seen: list[Any] = []

        class DetailHook(DeleteHook):
            async def delete_post(self, op, pk, result):
                seen.append((pk, result.success))
                return result.model_copy(update={"representation": f"Item({pk})"})

        service = DeleteService(mock_repo, hooks=(DetailHook(),))
        mock_repo.delete_by_pk.return_value = True

        result = await service.delete(mock_async_session, sample_uuid)

        assert seen == [(sample_uuid, True)]
        assert result.representation == f"Item({sample_uuid})"

    async def test_delete_multi_applies_own_delete_context_per_item_by_default(
        self, mock_repo, mock_async_session, sample_uuid
    ):
        """A hook that only defines delete_context gets it applied to every pk."""
        seen: list[Any] = []

        class PerItemHook(DeleteHook):
            @asynccontextmanager
            async def delete_context(self, op, pk):
                seen.append(pk)
                yield

        service = DeleteService(mock_repo, hooks=(PerItemHook(),))
        mock_repo.delete_by_pk_multi.return_value = 1

        await service.delete_multi(mock_async_session, [sample_uuid])

        assert seen == [sample_uuid]

    async def test_delete_multi_bulk_override_replaces_only_its_own_per_item_context(
        self, mock_repo, mock_async_session, sample_uuid
    ):
        """Overriding delete_context_multi replaces that hook's own per-item context."""
        calls: list[str] = []

        class BulkHook(DeleteHook):
            @asynccontextmanager
            async def delete_context(self, op, pk):
                calls.append("per_item")
                yield

            @asynccontextmanager
            async def delete_context_multi(self, op, pks):
                calls.append("bulk")
                yield

        service = DeleteService(mock_repo, hooks=(BulkHook(),))
        mock_repo.delete_by_pk_multi.return_value = 1

        await service.delete_multi(mock_async_session, [sample_uuid])

        assert calls == ["bulk"]

    @pytest.mark.parametrize("bulk_first", [True, False])
    async def test_delete_multi_bulk_override_does_not_suppress_other_hooks(
        self, mock_repo, mock_async_session, bulk_first
    ):
        """Regression: one hook's bulk delete context must not disable another's per-item one."""
        bulk_calls: list[str] = []
        per_item_seen: list[Any] = []

        class BulkHook(DeleteHook):
            @asynccontextmanager
            async def delete_context_multi(self, op, pks):
                bulk_calls.append("bulk")
                yield

        class PerItemHook(DeleteHook):
            @asynccontextmanager
            async def delete_context(self, op, pk):
                per_item_seen.append(pk)
                yield

        hooks = (BulkHook(), PerItemHook()) if bulk_first else (PerItemHook(), BulkHook())
        service = DeleteService(mock_repo, hooks=hooks)
        pks = [uuid.uuid4(), uuid.uuid4()]
        mock_repo.delete_by_pk_multi.return_value = 2

        await service.delete_multi(mock_async_session, pks)

        assert bulk_calls == ["bulk"]
        assert per_item_seen == pks

    @pytest.mark.parametrize(
        ("requested", "deleted_count", "expected_failed"),
        [
            (3, 3, 0),  # all deleted
            (3, 2, 1),  # one not found / not deleted
            (3, 0, 3),  # none deleted
            (1, 3, 0),  # deleted_count exceeds request -> clamped to 0
        ],
    )
    async def test_delete_multi_derives_failed_count_from_aggregate(
        self, mock_repo, mock_async_session, requested, deleted_count, expected_failed
    ):
        """failed_count is derived as max(0, requested - deleted_count), no extra query."""
        service = DeleteService(mock_repo)
        mock_repo.delete_by_pk_multi.return_value = deleted_count
        pks = [uuid.uuid4() for _ in range(requested)]

        result = await service.delete_multi(mock_async_session, pks)

        assert result.deleted_count == deleted_count
        assert result.failed_count == expected_failed
        mock_repo.delete_by_pk_multi.assert_called_once_with(mock_async_session, pks=pks)

    async def test_delete_post_multi_applies_per_item_post_when_all_deleted(self, mock_repo, mock_async_session):
        """The default bulk post applies per-item delete_post when every pk was deleted."""
        seen: list[Any] = []

        class PostHook(DeleteHook):
            async def delete_post(self, op, pk, result):
                seen.append((pk, result.success, result.identity))
                return result

        service = DeleteService(mock_repo, hooks=(PostHook(),))
        pks = [uuid.uuid4(), uuid.uuid4()]
        mock_repo.delete_by_pk_multi.return_value = 2

        result = await service.delete_multi(mock_async_session, pks)

        assert result.deleted_count == 2
        assert seen == [(pks[0], True, pks[0]), (pks[1], True, pks[1])]

    async def test_delete_post_multi_skips_per_item_post_on_partial_result(self, mock_repo, mock_async_session):
        """Should not fabricate per-item post-delete success for partial bulk results."""
        seen: list[Any] = []

        class PostHook(DeleteHook):
            async def delete_post(self, op, pk, result):
                seen.append(pk)
                return result

        service = DeleteService(mock_repo, hooks=(PostHook(),))
        pks = [uuid.uuid4(), uuid.uuid4()]
        mock_repo.delete_by_pk_multi.return_value = 1

        result = await service.delete_multi(mock_async_session, pks)

        assert result.deleted_count == 1
        assert result.failed_count == 1
        assert seen == []

    async def test_delete_post_multi_bulk_override_replaces_only_its_own_per_item_post(
        self, mock_repo, mock_async_session, sample_uuid
    ):
        """Overriding delete_post_multi replaces that hook's own per-item delete_post."""
        calls: list[str] = []

        class BulkPostHook(DeleteHook):
            async def delete_post(self, op, pk, result):
                calls.append("per_item")
                return result

            async def delete_post_multi(self, op, pks, result):
                calls.append("bulk")
                return result.model_copy(update={"meta": {"bulk": True}})

        service = DeleteService(mock_repo, hooks=(BulkPostHook(),))
        mock_repo.delete_by_pk_multi.return_value = 1

        result = await service.delete_multi(mock_async_session, [sample_uuid])

        assert calls == ["bulk"]
        assert result.meta == {"bulk": True}

    async def test_delete_post_multi_bulk_override_does_not_suppress_other_hooks(
        self, mock_repo, mock_async_session, sample_uuid
    ):
        """Regression: a bulk post override must not disable another hook's per-item post."""
        bulk_calls: list[str] = []
        per_item_seen: list[Any] = []

        class BulkPostHook(DeleteHook):
            async def delete_post_multi(self, op, pks, result):
                bulk_calls.append("bulk")
                return result

        class PerItemPostHook(DeleteHook):
            async def delete_post(self, op, pk, result):
                per_item_seen.append(pk)
                return result

        service = DeleteService(mock_repo, hooks=(BulkPostHook(), PerItemPostHook()))
        mock_repo.delete_by_pk_multi.return_value = 1

        await service.delete_multi(mock_async_session, [sample_uuid])

        assert bulk_calls == ["bulk"]
        assert per_item_seen == [sample_uuid]


# =============================================================================
# Tests for BaseGetServiceMixin
# =============================================================================


class TestBaseGetServiceMixin:
    """Tests for get service mixin."""

    async def test_get_calls_repo_get_by_pk(self, mock_repo, mock_async_session, mock_model, sample_uuid):
        """Should call repository get_by_pk method."""
        service = GetService(mock_repo)
        mock_repo.get_by_pk.return_value = mock_model

        result = await service.get(mock_async_session, sample_uuid)

        assert result == mock_model
        mock_repo.get_by_pk.assert_called_once_with(mock_async_session, pk=sample_uuid)

    async def test_get_returns_none_when_not_found(self, mock_repo, mock_async_session, sample_uuid):
        """Should return None when record not found."""
        service = GetService(mock_repo)
        mock_repo.get_by_pk.return_value = None

        result = await service.get(mock_async_session, sample_uuid)

        assert result is None

    async def test_get_with_post_get_hook(self, mock_repo, mock_async_session, mock_model, sample_uuid):
        """get_post can mutate/replace the fetched object."""

        class ModifyHook(GetHook):
            async def get_post(self, op, obj):
                if obj:
                    obj.name = "Modified by hook"
                return obj

        service = GetService(mock_repo, hooks=(ModifyHook(),))
        mock_repo.get_by_pk.return_value = mock_model

        result = await service.get(mock_async_session, sample_uuid)

        assert result is not None
        assert result.name == "Modified by hook"

    async def test_get_post_hook_receives_none_when_not_found(self, mock_repo, mock_async_session, sample_uuid):
        """get_post still runs, with None, when the row doesn't exist."""
        seen: list[Any] = []

        class SpyHook(GetHook):
            async def get_post(self, op, obj):
                seen.append(obj)
                return obj

        service = GetService(mock_repo, hooks=(SpyHook(),))
        mock_repo.get_by_pk.return_value = None

        assert await service.get(mock_async_session, sample_uuid) is None
        assert seen == [None]

    async def test_get_context_hook_wraps_the_repo_call(
        self, mock_repo, mock_async_session, mock_model, sample_uuid, hook_log
    ):
        """get_context is entered before, and exited after, the repository call."""

        class SpanHook(GetHook):
            @asynccontextmanager
            async def get_context(self, op, pk):
                hook_log.append("enter")
                try:
                    yield
                finally:
                    hook_log.append("exit")

        service = GetService(mock_repo, hooks=(SpanHook(),))
        mock_repo.get_by_pk.side_effect = lambda *a, **k: hook_log.append("repo") or mock_model

        await service.get(mock_async_session, sample_uuid)

        assert hook_log == ["enter", "repo", "exit"]


# =============================================================================
# Tests for BaseGetMultiServiceMixin
# =============================================================================


class _FilterHook(GetMultiHook):
    """Contributes one extra WHERE clause."""

    def __init__(self, name: str = "extra_filter"):
        self.clause = MagicMock(name=name)

    def get_multi_prepare_filters(self, op):
        return [self.clause]


class TestBaseGetMultiServiceMixin:
    """Tests for get multi service mixin."""

    async def test_get_multi_calls_repo_get_multi(self, mock_repo, mock_async_session, paginated):
        """Should call repository get_multi method."""
        service = GetMultiService(mock_repo)
        mock_repo.get_multi.return_value = paginated

        result = await service.get_multi(mock_async_session, query_options=ListQueryOptions(offset=0, limit=10))

        assert result == paginated
        mock_repo.get_multi.assert_called_once()

    async def test_get_multi_uses_default_query_options_when_omitted(self, mock_repo, mock_async_session, paginated):
        """A missing query_options becomes the ListQueryOptions default."""
        service = GetMultiService(mock_repo)
        mock_repo.get_multi.return_value = paginated

        await service.get_multi(mock_async_session)

        options = mock_repo.get_multi.call_args.kwargs["query_options"]
        assert options.offset == 0
        assert options.limit == 100
        assert list(options.where) == []

    async def test_get_multi_with_where_conditions(self, mock_repo, mock_async_session, paginated):
        """Should pass where conditions to repository."""
        service = GetMultiService(mock_repo)
        mock_repo.get_multi.return_value = paginated

        where_conditions = [MagicMock()]
        await service.get_multi(mock_async_session, query_options=ListQueryOptions(where=where_conditions))

        options = mock_repo.get_multi.call_args.kwargs["query_options"]
        assert options.where == where_conditions

    async def test_get_multi_merges_extra_filters(self, mock_repo, mock_async_session, paginated):
        """Should merge extra filters from the get_multi_prepare_filters hook."""
        hook = _FilterHook()
        service = GetMultiService(mock_repo, hooks=(hook,))
        mock_repo.get_multi.return_value = paginated

        await service.get_multi(mock_async_session)

        options = mock_repo.get_multi.call_args.kwargs["query_options"]
        assert list(options.where) == [hook.clause]

    async def test_get_multi_merges_where_list_with_extra_filters(self, mock_repo, mock_async_session, paginated):
        """Should merge a caller-supplied where list with hook filters."""
        hook = _FilterHook()
        service = GetMultiService(mock_repo, hooks=(hook,))
        mock_repo.get_multi.return_value = paginated

        user_filter = MagicMock(name="user_filter")
        await service.get_multi(mock_async_session, query_options=ListQueryOptions(where=[user_filter]))

        options = mock_repo.get_multi.call_args.kwargs["query_options"]
        assert list(options.where) == [user_filter, hook.clause]

    async def test_get_multi_merges_single_where_clause_with_extra_filters(
        self, mock_repo, mock_async_session, paginated
    ):
        """A bare (non-sequence) where clause is wrapped into a list with the hook filters."""
        hook = _FilterHook()
        service = GetMultiService(mock_repo, hooks=(hook,))
        mock_repo.get_multi.return_value = paginated

        single_clause = MagicMock(name="single_clause")
        assert not isinstance(single_clause, Sequence)
        await service.get_multi(mock_async_session, query_options=ListQueryOptions(where=single_clause))

        options = mock_repo.get_multi.call_args.kwargs["query_options"]
        assert list(options.where) == [single_clause, hook.clause]

    async def test_get_multi_leaves_single_where_clause_untouched_without_hooks(
        self, mock_repo, mock_async_session, paginated
    ):
        """No hook filters -> a bare where clause is passed through as-is."""
        service = GetMultiService(mock_repo)
        mock_repo.get_multi.return_value = paginated

        single_clause = MagicMock(name="single_clause")
        await service.get_multi(mock_async_session, query_options=ListQueryOptions(where=single_clause))

        options = mock_repo.get_multi.call_args.kwargs["query_options"]
        assert options.where is single_clause

    async def test_get_multi_where_none_becomes_extra_filters(self, mock_repo, mock_async_session, paginated):
        """where=None is replaced by the hook filters."""
        hook = _FilterHook()
        service = GetMultiService(mock_repo, hooks=(hook,))
        mock_repo.get_multi.return_value = paginated

        await service.get_multi(mock_async_session, query_options=ListQueryOptions(where=None))

        options = mock_repo.get_multi.call_args.kwargs["query_options"]
        assert list(options.where) == [hook.clause]

    async def test_get_multi_filters_from_several_hooks_are_concatenated_in_order(
        self, mock_repo, mock_async_session, paginated
    ):
        """Filters accumulate in hooks order."""
        first, second = _FilterHook("first"), _FilterHook("second")
        service = GetMultiService(mock_repo, hooks=(first, second))
        mock_repo.get_multi.return_value = paginated

        await service.get_multi(mock_async_session)

        options = mock_repo.get_multi.call_args.kwargs["query_options"]
        assert list(options.where) == [first.clause, second.clause]

    async def test_get_multi_post_hook_can_replace_result(self, mock_repo, mock_async_session, paginated):
        """get_multi_post may return a different PaginatedList."""
        replacement = PaginatedList(items=[], total_count=0, offset=0, limit=10)

        class ReplaceHook(GetMultiHook):
            async def get_multi_post(self, op, result):
                return replacement

        service = GetMultiService(mock_repo, hooks=(ReplaceHook(),))
        mock_repo.get_multi.return_value = paginated

        result = await service.get_multi(mock_async_session)

        assert result is replacement


# =============================================================================
# Executor guarantees
# =============================================================================


class TestExecutorOrdering:
    """Contexts enter forward and exit backward; prepare forward, post backward."""

    async def test_create_executes_hooks_in_documented_order(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model, hook_log
    ):
        service = CreateService(mock_repo, hooks=(RecordingHook("a", hook_log), RecordingHook("b", hook_log)))
        mock_repo.create.side_effect = lambda *a, **k: hook_log.append("repo:create") or mock_model

        result = await service.create(mock_async_session, mock_create_schema)

        assert result == mock_model
        assert hook_log == [
            "a:create_context:enter",
            "b:create_context:enter",
            "a:create_prepare_fields",
            "b:create_prepare_fields",
            "repo:create",
            "b:create_post",
            "a:create_post",
            "b:create_context:exit",
            "a:create_context:exit",
        ]
        # forward prepare order means the later hook wins on a shared key
        assert mock_repo.create.call_args.kwargs == {
            "obj_in": mock_create_schema,
            "a_field": "a",
            "b_field": "b",
        }

    async def test_update_executes_hooks_in_documented_order(
        self, mock_repo, mock_async_session, mock_update_schema, mock_model, sample_uuid, hook_log
    ):
        service = UpdateService(mock_repo, hooks=(RecordingHook("a", hook_log), RecordingHook("b", hook_log)))
        mock_repo.update_by_pk.side_effect = lambda *a, **k: hook_log.append("repo:update") or mock_model

        await service.patch(mock_async_session, sample_uuid, mock_update_schema)

        assert hook_log == [
            "a:update_context:enter",
            "b:update_context:enter",
            "a:update_prepare_fields",
            "b:update_prepare_fields",
            "repo:update",
            "b:update_post",
            "a:update_post",
            "b:update_context:exit",
            "a:update_context:exit",
        ]

    async def test_delete_executes_hooks_in_documented_order(
        self, mock_repo, mock_async_session, sample_uuid, hook_log
    ):
        service = DeleteService(mock_repo, hooks=(RecordingHook("a", hook_log), RecordingHook("b", hook_log)))
        mock_repo.delete_by_pk.side_effect = lambda *a, **k: hook_log.append("repo:delete") or True

        await service.delete(mock_async_session, sample_uuid)

        assert hook_log == [
            "a:delete_context:enter",
            "b:delete_context:enter",
            "repo:delete",
            "b:delete_post",
            "a:delete_post",
            "b:delete_context:exit",
            "a:delete_context:exit",
        ]

    async def test_get_executes_hooks_in_documented_order(
        self, mock_repo, mock_async_session, mock_model, sample_uuid, hook_log
    ):
        service = GetService(mock_repo, hooks=(RecordingHook("a", hook_log), RecordingHook("b", hook_log)))
        mock_repo.get_by_pk.side_effect = lambda *a, **k: hook_log.append("repo:get") or mock_model

        await service.get(mock_async_session, sample_uuid)

        assert hook_log == [
            "a:get_context:enter",
            "b:get_context:enter",
            "repo:get",
            "b:get_post",
            "a:get_post",
            "b:get_context:exit",
            "a:get_context:exit",
        ]

    async def test_get_multi_executes_hooks_in_documented_order(
        self, mock_repo, mock_async_session, paginated, hook_log
    ):
        service = GetMultiService(mock_repo, hooks=(RecordingHook("a", hook_log), RecordingHook("b", hook_log)))
        mock_repo.get_multi.side_effect = lambda *a, **k: hook_log.append("repo:list") or paginated

        await service.get_multi(mock_async_session)

        assert hook_log == [
            # Filters are collected inside the contexts, like every other
            # operation's *_prepare_* step, so a hook can filter on what its own
            # context set up.
            "a:get_multi_context:enter",
            "b:get_multi_context:enter",
            "a:get_multi_prepare_filters",
            "b:get_multi_prepare_filters",
            "repo:list",
            "b:get_multi_post",
            "a:get_multi_post",
            "b:get_multi_context:exit",
            "a:get_multi_context:exit",
        ]

    async def test_create_post_hooks_compose_in_reverse_order(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model
    ):
        """The last hook's create_post sees the repo object; the first sees its output."""

        class TagHook(CreateHook):
            def __init__(self, tag: str):
                self.tag = tag

            async def create_post(self, op, obj):
                obj.name = f"{obj.name}|{self.tag}"
                return obj

        service = CreateService(mock_repo, hooks=(TagHook("a"), TagHook("b")))
        mock_model.name = "base"
        mock_repo.create.return_value = mock_model

        result = await service.create(mock_async_session, mock_create_schema)

        assert result.name == "base|b|a"


class TestExecutorFailureIsolation:
    """A hook that raises in its context aborts the operation cleanly."""

    async def test_raising_create_context_blocks_repo_and_later_hooks(
        self, mock_repo, mock_async_session, mock_create_schema, hook_log
    ):
        class RaisingHook(CreateHook):
            @asynccontextmanager
            async def create_context(self, op, data):
                hook_log.append("raiser")
                raise BoomError("nope")
                yield  # pragma: no cover

        class SpanHook(CreateHook):
            def __init__(self, name: str):
                self.name = name

            @asynccontextmanager
            async def create_context(self, op, data):
                hook_log.append(f"{self.name}:enter")
                try:
                    yield
                finally:
                    hook_log.append(f"{self.name}:exit")

            def create_prepare_fields(self, op, data, fields):
                hook_log.append(f"{self.name}:fields")
                return fields

        service = CreateService(mock_repo, hooks=(SpanHook("early"), RaisingHook(), SpanHook("late")))

        with pytest.raises(BoomError):
            await service.create(mock_async_session, mock_create_schema)

        # repo never ran, the later hook's context never opened, the earlier one unwound
        mock_repo.create.assert_not_called()
        assert hook_log == ["early:enter", "raiser", "early:exit"]

    async def test_raising_delete_context_multi_blocks_repo(self, mock_repo, mock_async_session, sample_uuid):
        class RaisingHook(DeleteHook):
            @asynccontextmanager
            async def delete_context(self, op, pk):
                raise BoomError("nope")
                yield  # pragma: no cover

        service = DeleteService(mock_repo, hooks=(RaisingHook(),))

        with pytest.raises(BoomError):
            await service.delete_multi(mock_async_session, [sample_uuid])

        mock_repo.delete_by_pk_multi.assert_not_called()

    async def test_raising_get_multi_context_blocks_repo(self, mock_repo, mock_async_session, hook_log):
        class RaisingHook(GetMultiHook):
            @asynccontextmanager
            async def get_multi_context(self, op):
                raise BoomError("nope")
                yield  # pragma: no cover

        class SpanHook(GetMultiHook):
            @asynccontextmanager
            async def get_multi_context(self, op):
                hook_log.append("enter")
                try:
                    yield
                finally:
                    hook_log.append("exit")

        service = GetMultiService(mock_repo, hooks=(SpanHook(), RaisingHook()))

        with pytest.raises(BoomError):
            await service.get_multi(mock_async_session)

        mock_repo.get_multi.assert_not_called()
        assert hook_log == ["enter", "exit"]

    async def test_repo_failure_still_unwinds_every_context(
        self, mock_repo, mock_async_session, mock_create_schema, hook_log
    ):
        service = CreateService(mock_repo, hooks=(RecordingHook("a", hook_log), RecordingHook("b", hook_log)))
        mock_repo.create.side_effect = BoomError("db down")

        with pytest.raises(BoomError):
            await service.create(mock_async_session, mock_create_schema)

        assert hook_log[-2:] == ["b:create_context:exit", "a:create_context:exit"]
        assert "a:create_post" not in hook_log
        assert "b:create_post" not in hook_log


class TestOperationState:
    """``Operation.state`` is the sanctioned place for per-call scratch data."""

    async def test_state_is_shared_between_context_and_post_within_one_call(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model
    ):
        seen: list[Any] = []

        class StatefulHook(CreateHook):
            @asynccontextmanager
            async def create_context(self, op, data):
                op.state["captured"] = data.name
                yield

            async def create_post(self, op, obj):
                seen.append(op.state["captured"])
                return obj

        service = CreateService(mock_repo, hooks=(StatefulHook(),))
        mock_repo.create.return_value = mock_model

        await service.create(mock_async_session, MockCreateSchema(name="first"))
        await service.create(mock_async_session, MockCreateSchema(name="second"))

        assert seen == ["first", "second"]

    async def test_state_is_fresh_for_each_service_call(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model
    ):
        """A value written in one call must not leak into the next."""
        snapshots: list[dict] = []
        ops: list[Operation] = []

        class LeakyHook(CreateHook):
            @asynccontextmanager
            async def create_context(self, op, data):
                snapshots.append(dict(op.state))
                ops.append(op)
                op.state["leak"] = "value"
                yield

        service = CreateService(mock_repo, hooks=(LeakyHook(),))
        mock_repo.create.return_value = mock_model

        await service.create(mock_async_session, mock_create_schema)
        await service.create(mock_async_session, mock_create_schema)

        assert snapshots == [{}, {}]
        assert ops[0] is not ops[1]
        assert ops[0].state is not ops[1].state

    async def test_state_is_fresh_across_different_operations(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model, sample_uuid
    ):
        """create and get on the same service each get their own Operation.state."""
        states: list[dict] = []

        class BothHook(CreateHook, GetHook):
            @asynccontextmanager
            async def create_context(self, op, data):
                states.append(op.state)
                op.state["from_create"] = True
                yield

            @asynccontextmanager
            async def get_context(self, op, pk):
                states.append(op.state)
                yield

        service = FullService(mock_repo, hooks=(BothHook(),))
        mock_repo.create.return_value = mock_model
        mock_repo.get_by_pk.return_value = mock_model

        await service.create(mock_async_session, mock_create_schema)
        await service.get(mock_async_session, sample_uuid)

        assert states[0] is not states[1]
        assert states[1] == {}

    async def test_state_is_shared_between_hooks_of_the_same_call(
        self, mock_repo, mock_async_session, mock_create_schema, mock_model
    ):
        """All hooks in one call see the same Operation instance."""
        seen: list[Any] = []

        class WriterHook(CreateHook):
            @asynccontextmanager
            async def create_context(self, op, data):
                op.state["written_by"] = "writer"
                yield

        class ReaderHook(CreateHook):
            @asynccontextmanager
            async def create_context(self, op, data):
                seen.append(op.state.get("written_by"))
                yield

        service = CreateService(mock_repo, hooks=(WriterHook(), ReaderHook()))
        mock_repo.create.return_value = mock_model

        await service.create(mock_async_session, mock_create_schema)

        assert seen == ["writer"]

    async def test_create_multi_shares_one_operation_across_items(self, mock_repo, mock_async_session, mock_model):
        """The per-item fallback reuses the same Operation (hence the same state)."""
        ops: list[Operation] = []

        class CountingHook(CreateHook):
            @asynccontextmanager
            async def create_context(self, op, data):
                ops.append(op)
                op.state["count"] = op.state.get("count", 0) + 1
                yield

        service = CreateService(mock_repo, hooks=(CountingHook(),))
        mock_repo.create_multi.return_value = [mock_model, mock_model]

        await service.create_multi(mock_async_session, [MockCreateSchema(name="A"), MockCreateSchema(name="B")])

        assert len(ops) == 2
        assert ops[0] is ops[1]
        assert ops[0].state["count"] == 2


# =============================================================================
# Response schema sanity (delete responses produced by the service)
# =============================================================================


class TestDeleteResponseShapes:
    async def test_delete_returns_delete_response(self, mock_repo, mock_async_session, sample_uuid):
        service = DeleteService(mock_repo)
        mock_repo.delete_by_pk.return_value = True

        result = await service.delete(mock_async_session, sample_uuid)

        assert isinstance(result, DeleteResponse)

    async def test_delete_multi_returns_multiple_delete_response(self, mock_repo, mock_async_session, sample_uuid):
        service = DeleteService(mock_repo)
        mock_repo.delete_by_pk_multi.return_value = 1

        result = await service.delete_multi(mock_async_session, [sample_uuid])

        assert isinstance(result, MultipleDeleteResponse)
