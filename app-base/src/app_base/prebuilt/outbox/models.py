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

    aggregate_type: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Type of the aggregate that the event belongs to (e.g., 'User', 'Product')",
    )
    aggregate_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Identifier of the aggregate instance (e.g., user ID, product ID)",
    )
    event_type: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="The type of event that occurred (e.g., 'UserCreated', 'ProductUpdated')"
    )
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, comment="The event data in JSON format")
    status: Mapped[EventStatus] = mapped_column(
        EnumColumn(EventStatus),
        nullable=False,
        default=EventStatus.PENDING,
        index=True,
        comment="Current status of the event (PENDING, PROCESSING, PUBLISHED, FAILED)",
    )
    retry_count: Mapped[int] = mapped_column(
        default=0, comment="Number of times the event publication has been retried"
    )
    processed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when the event was last processed or attempted to be published",
    )
