import functools

from pydantic import EmailStr, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_base.config.util import get_env_file_path


class AuthSettings(BaseSettings):
    FIRST_USER_EMAIL: EmailStr
    FIRST_USER_PASSWORD: SecretStr

    SECRET_KEY: SecretStr  # openssl rand -hex 64

    # JWT
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_ISSUER: str = Field(default="app-base")
    JWT_AUDIENCE: str = Field(default="app-base")
    JWT_LEEWAY_SECONDS: int = Field(default=10, description="Clock skew tolerance when validating exp/nbf")

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=10)

    # Optional: refresh token expiration (only used if you implement refresh flow in your app)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=14)

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        extra="ignore",
    )


@functools.lru_cache
def get_auth_settings():
    return AuthSettings(**{})
