import uuid
from datetime import datetime
from typing import Any

from pydantic import UUID4, BaseModel, Field

from app_layer_base.utils.time_util import get_current_utc_time


class DomainEvent(BaseModel):
    """
    Standard schema for domain events.

    Designed based on the CloudEvents 1.0 specification.
    https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md

    Attributes:
        id: Unique event identifier
        source: Event origin source (e.g., "/orders/service", "urn:myapp:orders")
        type: Event type (e.g., "order.created", "user.registered")
        data: Event data
        meta: Additional metadata (aggregate_type, aggregate_id, correlation_id, etc.)
        time: Event occurrence time (UTC)

    Example:
        ```python
        event = DomainEvent(
            source="/orders/service",
            type="order.created",
            data={"order_id": "123", "total": 100.0},
            meta={"correlation_id": "abc-123"},
        )
        ```
    """

    id: UUID4 = Field(default_factory=uuid.uuid4, description="Unique event identifier")
    source: str = Field(
        default="",
        description="Event origin source (e.g., '/orders/service')",
    )
    type: str = Field(..., description="Event type (e.g., 'order.created')")
    data: dict[str, Any] = Field(default_factory=dict, description="Event data")
    meta: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    time: datetime = Field(
        default_factory=get_current_utc_time,
        description="Event occurrence time (UTC)",
    )

    def to_message(self) -> dict[str, Any]:
        """Converts to CloudEvents 1.0 compatible format."""
        return {
            "specversion": "1.0",
            "id": str(self.id),
            "source": self.source,
            "type": self.type,
            "time": self.time.isoformat(),
            "data": self.data,
            **{f"x-meta-{k}": v for k, v in self.meta.items()},
        }
