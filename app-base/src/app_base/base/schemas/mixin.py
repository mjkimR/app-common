import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class UUIDSchemaMixin(BaseModel):
    id: uuid.UUID


class TimestampSchemaMixin(BaseModel):
    created_at: datetime
    updated_at: datetime


class AuditSchemaMixin(BaseModel):
    created_by: uuid.UUID
    updated_by: Optional[uuid.UUID] = None


class SoftDeleteSchemaMixin(BaseModel):
    is_deleted: bool
    deleted_at: Optional[datetime] = None


class TaggableSchemaMixin(BaseModel):
    tags: Optional[list[str]] = None
