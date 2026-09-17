from datetime import datetime
from typing import Any

from app_layer_base.base.models.mixin import Base
from sqlalchemy import JSON, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column


class SearchIndexState(Base):
    """One synchronization marker and lock row per index/scope/profile."""

    __tablename__ = "search_index_states"
    index_name: Mapped[str] = mapped_column(String(128), primary_key=True)
    scope_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    profile_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_result: Mapped[dict[str, Any] | None] = mapped_column(JSON)
