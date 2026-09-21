from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class MachineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
    scopes: list[str] = Field(default_factory=list, max_length=50)


class MachineUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scopes: list[str] | None = Field(default=None, max_length=50)
    is_active: bool | None = None


class MachineRead(MachineCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    is_active: bool


class KeyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=100)
    expires_at: AwareDatetime | None = None


class KeyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    machine_id: UUID
    label: str
    created_at: datetime
    expires_at: datetime | None
    revoked_at: datetime | None


class KeyIssued(KeyRead):
    key: str = Field(repr=False, description="Shown once; store it before leaving this response")


class MachinePrincipal(BaseModel):
    model_config = ConfigDict(frozen=True)
    machine_id: UUID
    key_id: UUID
    name: str
    scopes: frozenset[str]
