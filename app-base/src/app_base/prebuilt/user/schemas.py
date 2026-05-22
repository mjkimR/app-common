from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from app_base.base.schemas.mixin import TimestampSchemaMixin, UUIDSchemaMixin


class UserCreate(BaseModel):
    firstname: str = Field(..., description="The user's first name.")
    lastname: str = Field(..., description="The user's last name.")
    email: EmailStr = Field(..., description="The user's email address.")
    password: SecretStr = Field(..., min_length=8, description="The user's password.")
    profile_image_url: str | None = Field(default=None, description="URL of the user's profile image.")
    phone_number: str | None = Field(default=None, description="The user's phone number.")
    locale: str | None = Field(default=None, description="The user's preferred locale.")
    timezone: str | None = Field(default=None, description="The user's preferred timezone.")
    extra: dict | None = Field(default=None, description="Additional user metadata.")


class UserDbCreate(UserCreate):
    hashed_password: str | None = Field(default=None, description="The user's hashed password.")
    is_active: bool = Field(default=True, description="Whether the user account is active.")
    is_verified: bool = Field(default=False, description="Whether the user's email has been verified.")
    is_superadmin: bool = Field(default=False, description="Whether the user has superadmin privileges.")


class UserUpdate(BaseModel):
    firstname: str | None = Field(default=None, description="The user's first name.")
    lastname: str | None = Field(default=None, description="The user's last name.")
    email: EmailStr | None = Field(default=None, description="The user's email address.")
    password: SecretStr | None = Field(default=None, description="The user's password.")
    profile_image_url: str | None = Field(default=None, description="URL of the user's profile image.")
    phone_number: str | None = Field(default=None, description="The user's phone number.")
    locale: str | None = Field(default=None, description="The user's preferred locale.")
    timezone: str | None = Field(default=None, description="The user's preferred timezone.")


class UserUpdateAdmin(UserUpdate):
    extra: dict | None = Field(default=None, description="Additional user metadata.")
    is_active: bool | None = Field(default=None, description="Whether the user account is active.")
    is_verified: bool | None = Field(default=None, description="Whether the user's email has been verified.")
    is_superadmin: bool | None = Field(default=None, description="Whether the user account is super admin.")


class UserDbUpdate(UserUpdateAdmin):
    hashed_password: str | None = Field(default=None, description="The user's hashed password.")


class UserRead(UUIDSchemaMixin, TimestampSchemaMixin, BaseModel):
    firstname: str = Field(..., description="The user's first name.")
    lastname: str = Field(..., description="The user's last name.")
    email: EmailStr = Field(..., description="The user's email address.")
    profile_image_url: str | None = Field(default=None, description="URL of the user's profile image.")
    phone_number: str | None = Field(default=None, description="The user's phone number.")
    locale: str | None = Field(default=None, description="The user's preferred locale.")
    timezone: str | None = Field(default=None, description="The user's preferred timezone.")

    model_config = ConfigDict(from_attributes=True)


class UserReadAdmin(UserRead):
    is_active: bool = Field(..., description="Whether the user account is active.")
    is_verified: bool = Field(..., description="Whether the user's email has been verified.")
    is_superadmin: bool = Field(..., description="Whether the user has superadmin privileges.")
    last_login_at: datetime | None = Field(default=None, description="The timestamp of the user's last login.")
    extra: dict | None = Field(default=None, description="Additional user metadata.")

    model_config = ConfigDict(from_attributes=True)
