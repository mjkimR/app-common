from datetime import datetime
from uuid import UUID

from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class Machine(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "api_key_machines"
    name: Mapped[str] = mapped_column(String(100), unique=True)
    scopes: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(default=True)


class MachineKey(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "api_keys"
    machine_id: Mapped[UUID] = mapped_column(ForeignKey("api_key_machines.id"), index=True)
    label: Mapped[str] = mapped_column(String(100))
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
