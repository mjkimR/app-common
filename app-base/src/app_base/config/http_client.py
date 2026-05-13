import functools

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_base.config.util import get_env_file_path


class HTTPClientSettings(BaseSettings):
    """
    Settings for the global HTTP client (httpx).
    Defaults match httpx standard defaults.
    """

    TIMEOUT: float = Field(default=5.0)
    MAX_CONNECTIONS: int = Field(default=100)
    MAX_KEEPALIVE_CONNECTIONS: int = Field(default=20)
    KEEPALIVE_EXPIRY: float = Field(default=5.0)

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="HTTP_CLIENT_",
        extra="ignore",
    )


@functools.lru_cache
def get_http_client_settings() -> HTTPClientSettings:
    """Returns a cached instance of the HTTP client settings."""
    return HTTPClientSettings()
