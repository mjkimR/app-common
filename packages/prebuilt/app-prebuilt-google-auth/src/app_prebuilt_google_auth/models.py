from datetime import datetime
from uuid import UUID

from app_layer_base.base.models.mixin import Base
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class GoogleLoginFlow(Base):
    """Short-lived secrets. State and exchange identifiers are stored only as hashes."""

    __tablename__ = "google_login_flows"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    browser_hash: Mapped[str] = mapped_column(String(64))
    nonce: Mapped[str | None] = mapped_column(String(128))
    verifier: Mapped[str | None] = mapped_column(String(128))
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
