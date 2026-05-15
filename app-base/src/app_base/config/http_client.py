import functools

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_base.config.util import get_env_file_path


class HTTPClientSettings(BaseSettings):
    """
    Settings for the global HTTP client (httpx).
    Defaults match httpx standard defaults.
    """

    TIMEOUT: float = Field(default=5.0, description="Default timeout in seconds for HTTP requests")
    MAX_CONNECTIONS: int = Field(
        default=100, description="Maximum number of concurrent HTTP connections in the connection pool"
    )
    MAX_KEEPALIVE_CONNECTIONS: int = Field(
        default=20, description="Maximum number of keep-alive connections to maintain in the pool"
    )
    KEEPALIVE_EXPIRY: float = Field(
        default=5.0, description="Time in seconds before an idle keep-alive connection is closed"
    )

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        env_prefix="HTTP_CLIENT_",
        extra="ignore",
    )


@functools.lru_cache
def get_http_client_settings() -> HTTPClientSettings:
    """Returns a cached instance of the HTTP client settings."""
    return HTTPClientSettings()
