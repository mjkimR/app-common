import functools

from pydantic import EmailStr, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    FIRST_USER_EMAIL: EmailStr = Field(description="Email address of the first superuser created on startup")
    FIRST_USER_PASSWORD: SecretStr = Field(description="Password for the first superuser account created on startup")

    SECRET_KEY: SecretStr = Field(description="Secret key used for signing tokens. Generate with: openssl rand -hex 64")

    REGISTRATION_REQUIRE_APPROVAL: bool = Field(
        default=False, description="New external identities require administrator approval"
    )

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

    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=14,
        description="Lifetime of a refresh token in days. Every refresh issues a new one, so this is how long a "
        "session survives without being used",
    )

    FIRST_USER_SYNC_PASSWORD: bool = Field(
        default=False,
        description="Keep the first superuser's password equal to FIRST_USER_PASSWORD on every startup, for "
        "deployments whose secret store is the source of truth. Off: the password is only set at creation",
    )

    # Failed-login lockout, per caller and per process
    LOGIN_MAX_FAILURES: int = Field(
        default=5, ge=1, description="Failed logins within the window that lock a caller out"
    )
    LOGIN_FAILURE_WINDOW_SECONDS: int = Field(default=60, ge=1, description="Window in which failed logins are counted")
    LOGIN_LOCKOUT_SECONDS: int = Field(default=300, ge=1, description="How long a locked-out caller is refused")

    model_config = SettingsConfigDict(
        extra="ignore",
    )


@functools.lru_cache
def get_auth_settings():
    return AuthSettings(**{})
