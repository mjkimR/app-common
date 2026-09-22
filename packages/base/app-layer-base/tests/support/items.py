import uuid

from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from app_layer_base.base.repos.base import BaseRepository
from app_layer_base.base.services.base import (
    BaseCreateServiceMixin,
    BaseDeleteServiceMixin,
    BaseGetMultiServiceMixin,
    BaseGetServiceMixin,
    BaseUpdateServiceMixin,
)
from app_layer_base.base.services.exists_check_hook import ExistsCheckHook
from app_layer_base.base.services.user_aware_hook import UserAwareHook, UserContextKwargs
from pydantic import BaseModel
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column


class IntegrationItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "integration_items"
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(nullable=True)


class ItemCreate(BaseModel):
    name: str
    description: str | None = None


class ItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ItemRepository(BaseRepository[IntegrationItem, ItemCreate, ItemUpdate, ItemUpdate]):
    model = IntegrationItem


class ItemService(
    BaseCreateServiceMixin,
    BaseUpdateServiceMixin,
    BaseGetServiceMixin,
    BaseGetMultiServiceMixin,
    BaseDeleteServiceMixin,
):
    def __init__(self, repo: ItemRepository):
        self._repo = repo
        # Existence is checked first, so a missing row fails before anything else runs.
        self.hooks = (ExistsCheckHook(), UserAwareHook())

    @property
    def repo(self):
        return self._repo

    @property
    def context_model(self):
        return UserContextKwargs
