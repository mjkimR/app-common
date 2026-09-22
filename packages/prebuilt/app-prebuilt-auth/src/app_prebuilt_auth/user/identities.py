"""Optional provider identities; import when composing external login providers."""

from uuid import UUID

from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class ExternalIdentity(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "user_external_identities"
    __table_args__ = (UniqueConstraint("issuer", "subject", name="uq_user_external_identity"),)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    issuer: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(255))
