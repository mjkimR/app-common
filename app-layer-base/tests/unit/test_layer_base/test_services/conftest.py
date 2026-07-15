"""
Shared fixtures for services hook unit tests.
Reuses mock models/repos from `test_layer_base.mock_models`.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app_layer_base.base.repos.base import BaseRepository
from app_layer_base.base.schemas.delete_resp import DeleteResponse, MultipleDeleteResponse
from app_layer_base.base.services.base import BaseContextKwargs
from app_layer_base.base.services.hooks import Operation
from test_layer_base.mock_models import MockChildRepository, MockCompositeRepository, MockRepository

# =============================================================================
# Common Service Builder Helper
# =============================================================================


def make_repo_mock(repo_cls: type[BaseRepository] = MockRepository) -> AsyncMock:
    """Create a repository-like AsyncMock with common attributes set."""
    real = repo_cls()
    repo = AsyncMock(spec=repo_cls)
    repo.primary_keys = real.primary_keys
    repo.model = repo_cls.model
    repo.model_name = repo_cls.model_name
    repo.model_repr = real.model_repr
    repo.normalize_pk = real.normalize_pk
    repo.normalize_pk_as_str = real.normalize_pk_as_str
    return repo


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_repo():
    return make_repo_mock()


@pytest.fixture
def child_repo_mock():
    """Repo mock for MockChildModel, which carries parent FK columns."""
    return make_repo_mock(MockChildRepository)


@pytest.fixture
def composite_repo_mock():
    """Repo mock for a model with a two-column primary key."""
    return make_repo_mock(MockCompositeRepository)


@pytest.fixture
def sample_uuid():
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def mock_delete_response():
    return DeleteResponse(success=True)


@pytest.fixture
def mock_failed_delete_response():
    return DeleteResponse(success=False)


@pytest.fixture
def mock_multiple_delete_response():
    return MultipleDeleteResponse(deleted_count=2)


@pytest.fixture
def mock_async_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    # A real dict so register_after_commit can queue on session.info like a live session.
    session.info = {}
    return session


@pytest.fixture
def base_context() -> BaseContextKwargs:
    return {}


@pytest.fixture
def user_context():
    return {"user_id": uuid.uuid4()}


@pytest.fixture
def base_op(mock_async_session, mock_repo) -> Operation:
    """An Operation over the plain MockModel repo with an empty context.

    Hooks are now standalone objects, so most assertions can be made by handing a
    hook an Operation directly -- no service required.
    """
    return Operation(session=mock_async_session, context={}, repo=mock_repo)
