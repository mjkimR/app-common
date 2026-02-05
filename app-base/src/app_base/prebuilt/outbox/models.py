import datetime
import enum
from typing import Any, Optional

from app_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import JSON, DateTime, String
from sqlalchemy import Enum as EnumColumn
from sqlalchemy.orm import Mapped, mapped_column


class EventStatus(str, enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"


class Outbox(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "outbox"

    aggregate_type: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    aggregate_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(255), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[EventStatus] = mapped_column(
        EnumColumn(EventStatus), nullable=False, default=EventStatus.PENDING, index=True
    )

    retry_count: Mapped[int] = mapped_column(default=0)
    processed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
