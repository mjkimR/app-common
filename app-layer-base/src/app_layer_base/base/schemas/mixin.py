import uuid
from datetime import datetime

from pydantic import BaseModel


class UUIDSchemaMixin(BaseModel):
    id: uuid.UUID


class TimestampSchemaMixin(BaseModel):
    created_at: datetime
    updated_at: datetime


class AuditSchemaMixin(BaseModel):
    created_by: uuid.UUID
    updated_by: uuid.UUID | None = None


class SoftDeleteSchemaMixin(BaseModel):
    is_deleted: bool
    deleted_at: datetime | None = None


class TaggableSchemaMixin(BaseModel):
    tags: list[str] | None = None
