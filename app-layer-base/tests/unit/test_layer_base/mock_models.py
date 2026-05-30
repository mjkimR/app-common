from app_layer_base.base.models.mixin import Base, SoftDeleteMixin, TimestampMixin, UUIDMixin
from app_layer_base.base.repos.base import BaseRepository
from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

# =============================================================================
# Mock Models
# =============================================================================


class MockModel(Base, UUIDMixin, TimestampMixin):
    """Mock model for testing repository operations."""

    __tablename__ = "mock_items"

    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)


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
    description: str | None = None


class MockUpdateSchema(BaseModel):
    """Schema for updating mock items."""

    name: str | None = None
    description: str | None = None


# =============================================================================
# Mock Repository
# =============================================================================


class MockRepository(BaseRepository[MockModel, MockCreateSchema, MockUpdateSchema, MockUpdateSchema]):
    """Mock repository for testing."""

    model = MockModel


class MockSoftDeleteRepository(
    BaseRepository[MockSoftDeleteModel, MockCreateSchema, MockUpdateSchema, MockUpdateSchema]
):
    """Mock repository with soft delete model."""

    model = MockSoftDeleteModel
