import uuid

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


class MockChildModel(Base, UUIDMixin, TimestampMixin):
    """Child model carrying FK columns to a parent -- single key and composite key."""

    __tablename__ = "mock_child_items"

    name: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    parent_tenant_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    parent_code: Mapped[str | None] = mapped_column(String(50), nullable=True)


class MockCompositeModel(Base, TimestampMixin):
    """Mock model with a two-column primary key."""

    __tablename__ = "mock_composite_items"

    tenant_id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)


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


class MockChildRepository(BaseRepository[MockChildModel, MockCreateSchema, MockUpdateSchema, MockUpdateSchema]):
    """Mock repository for the child model."""

    model = MockChildModel


class MockCompositeRepository(BaseRepository[MockCompositeModel, MockCreateSchema, MockUpdateSchema, MockUpdateSchema]):
    """Mock repository for the composite-primary-key model."""

    model = MockCompositeModel
