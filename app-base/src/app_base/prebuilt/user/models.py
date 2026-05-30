from datetime import datetime

from app_layer_base.base.models.mixin import Base, TimestampMixin, UUIDMixin
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column


class User(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "users"

    lastname: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="The user's last name.")
    firstname: Mapped[str] = mapped_column(String(255), comment="The user's first name.")
    email: Mapped[str] = mapped_column(String(320), unique=True, comment="The user's email address (unique).")
    hashed_password: Mapped[str | None] = mapped_column(
        String(255), nullable=True, comment="Hashed password for traditional login (optional for social logins)."
    )
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="Additional user metadata in JSON format.")

    is_active: Mapped[bool] = mapped_column(default=True, comment="Whether the user account is active.")
    is_verified: Mapped[bool] = mapped_column(
        default=False, comment="Whether the user's email address has been verified."
    )
    is_superadmin: Mapped[bool] = mapped_column(
        default=False, comment="Whether the user has superadmin privileges (can skip RBAC checks)."
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        nullable=True, comment="Timestamp of the user's last successful login."
    )
    profile_image_url: Mapped[str | None] = mapped_column(
        String(2048), nullable=True, comment="URL to the user's profile image."
    )
    phone_number: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="The user's phone number.")
    locale: Mapped[str | None] = mapped_column(
        String(20), nullable=True, comment="The user's preferred locale (e.g., 'en_US', 'ko_KR')."
    )
    timezone: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="The user's preferred timezone (e.g., 'Asia/Seoul')."
    )
