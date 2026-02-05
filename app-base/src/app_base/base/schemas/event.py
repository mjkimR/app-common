import uuid
from datetime import datetime
from typing import Any, TypeVar

from pydantic import UUID4, BaseModel, Field

from app_base.utils.time_util import get_current_utc_time

TPayload = TypeVar("TPayload", bound=BaseModel)


class DomainEvent(BaseModel):
    """
    Standard schema for domain events.

    Designed based on the CloudEvents 1.0 specification.
    https://github.com/cloudevents/spec/blob/v1.0.2/cloudevents/spec.md

    Attributes:
        id: Unique event identifier
        source: Event origin source (e.g., "/orders/service", "urn:myapp:orders")
        event_type: Event type (e.g., "order.created", "user.registered")
        payload: Event data
        meta: Additional metadata (aggregate_type, aggregate_id, correlation_id, etc.)
        occurred_at: Event occurrence time (UTC)

    Example:
        ```python
        event = DomainEvent(
            source="/orders/service",
            event_type="order.created",
            payload={"order_id": "123", "total": 100.0},
            meta={"correlation_id": "abc-123"},
        )
        ```
    """

    id: UUID4 = Field(default_factory=uuid.uuid4, description="Unique event identifier")
    source: str = Field(
        default="",
        description="Event origin source (e.g., '/orders/service')",
    )
    event_type: str = Field(..., description="Event type (e.g., 'order.created')")
    payload: dict[str, Any] = Field(default_factory=dict, description="Event data")
    meta: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    occurred_at: datetime = Field(
        default_factory=get_current_utc_time,
        description="Event occurrence time (UTC)",
    )

    def parse_payload(self, schema: type[TPayload]) -> TPayload:
        """Parses the payload into the specified schema."""
        return schema.model_validate(self.payload)

    def to_cloudevents_dict(self) -> dict[str, Any]:
        """Converts to CloudEvents 1.0 compatible format."""
        return {
            "specversion": "1.0",
            "id": str(self.id),
            "source": self.source,
            "type": self.event_type,
            "time": self.occurred_at.isoformat(),
            "data": self.payload,
            **{f"x-meta-{k}": v for k, v in self.meta.items()},
        }
