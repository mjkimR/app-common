import functools

from pydantic import EmailStr, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_base.config.util import get_env_file_path


class AuthSettings(BaseSettings):
    FIRST_USER_EMAIL: EmailStr
    FIRST_USER_PASSWORD: SecretStr

    SECRET_KEY: SecretStr  # openssl rand -hex 64
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=10)

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        extra="ignore",
    )


@functools.lru_cache
def get_auth_settings():
    return AuthSettings()  # type: ignore
