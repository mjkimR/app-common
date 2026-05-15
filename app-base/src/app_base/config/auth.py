import functools

from pydantic import EmailStr, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_base.config.util import get_env_file_path


class AuthSettings(BaseSettings):
    FIRST_USER_EMAIL: EmailStr = Field(description="Email address of the first superuser created on startup")
    FIRST_USER_PASSWORD: SecretStr = Field(description="Password for the first superuser account created on startup")

    SECRET_KEY: SecretStr = Field(description="Secret key used for signing tokens. Generate with: openssl rand -hex 64")

    # JWT
    JWT_ALGORITHM: str = Field(default="HS256", description="Algorithm used for JWT signing (e.g. HS256, RS256)")
    JWT_ISSUER: str = Field(default="app-base", description="Identifies the principal that issued the JWT (iss claim)")
    JWT_AUDIENCE: str = Field(
        default="app-base", description="Identifies the recipients that the JWT is intended for (aud claim)"
    )
    JWT_LEEWAY_SECONDS: int = Field(
        default=10, description="Clock skew tolerance in seconds when validating exp/nbf claims"
    )

    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=10, description="Lifetime of an access token in minutes")

    # Optional: refresh token expiration (only used if you implement refresh flow in your app)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=14, description="Lifetime of a refresh token in days (only used if refresh flow is implemented)"
    )

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        extra="ignore",
    )


@functools.lru_cache
def get_auth_settings():
    return AuthSettings(**{})
