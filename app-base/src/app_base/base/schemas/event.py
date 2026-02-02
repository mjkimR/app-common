import uuid
from datetime import datetime
from typing import TypeVar

from pydantic import UUID4, BaseModel, Field

from app_base.utils.time_util import get_current_utc_time

TPayload = TypeVar("TPayload", bound=BaseModel)


class DomainEvent(BaseModel):
    id: UUID4 = Field(default_factory=uuid.uuid4)
    event_type: str
    payload: dict
    meta: dict = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=get_current_utc_time)

    def parse_payload(self, schema: type[TPayload]) -> TPayload:
        return schema.model_validate(self.payload)
