"""
Conftest for base module unit app_tests.
Provides mock models, repositories, and services for testing.
"""

import datetime
import uuid
from typing import Optional
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app_base.base.models.mixin import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app_base.base.repos.base import BaseRepository

# =============================================================================
# Mock Models
# =============================================================================


class MockModel(Base, UUIDMixin, TimestampMixin):
    """Mock model for testing repository operations."""

    __tablename__ = "mock_items"

    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class MockSoftDeleteModel(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """Mock model with soft delete for testing."""

    __tablename__ = "mock_soft_delete_items"

    name: Mapped[str] = mapped_column(String(100))


# =============================================================================
# Mock Schemas
# =============================================================================


class MockCreateSchema(BaseModel):
    """Schema for creating mock items."""

    name: str
    description: Optional[str] = None


class MockUpdateSchema(BaseModel):
    """Schema for updating mock items."""

    name: Optional[str] = None
    description: Optional[str] = None


# =============================================================================
# Mock Repository
# =============================================================================


class MockRepository(BaseRepository[MockModel, MockCreateSchema, MockUpdateSchema]):
    """Mock repository for testing."""

    model = MockModel


class MockSoftDeleteRepository(BaseRepository[MockSoftDeleteModel, MockCreateSchema, MockUpdateSchema]):
    """Mock repository with soft delete model."""

    model = MockSoftDeleteModel


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_model():
    """Create a mock model instance."""
    model = MockModel(
        id=uuid.uuid4(),
        name="Test Item",
        description="Test Description",
        created_at=datetime.datetime.now(datetime.timezone.utc),
        updated_at=datetime.datetime.now(datetime.timezone.utc),
    )
    return model


@pytest.fixture
def mock_repository():
    """Create a MockRepository instance."""
    return MockRepository()


@pytest.fixture
def mock_soft_delete_repository():
    """Create a MockSoftDeleteRepository instance."""
    return MockSoftDeleteRepository()


@pytest.fixture
def mock_async_session():
    """Create a fully mocked async session."""
    session = AsyncMock()
    session.execute = AsyncMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.add = MagicMock()
    session.get = AsyncMock()
    return session


@pytest.fixture
def sample_uuid():
    """Provide a consistent UUID for testing."""
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


@pytest.fixture
def mock_create_schema():
    """Create a sample create schema."""
    return MockCreateSchema(name="New Item", description="New Description")


@pytest.fixture
def mock_update_schema():
    """Create a sample update schema."""
    return MockUpdateSchema(name="Updated Item")
