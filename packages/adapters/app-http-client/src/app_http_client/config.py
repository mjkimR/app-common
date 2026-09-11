import functools

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HTTPClientSettings(BaseSettings):
    """
    Settings for the global HTTP client (httpx).
    Defaults match httpx standard defaults.
    """

    timeout: float = Field(
        default=5.0,
        description="Default timeout in seconds for HTTP requests",
        validation_alias="HTTP_TIMEOUT",
    )
    max_connections: int = Field(
        default=100,
        description="Maximum number of concurrent HTTP connections in the connection pool",
        validation_alias="HTTP_MAX_CONNECTIONS",
    )
    max_keepalive_connections: int = Field(
        default=20,
        description="Maximum number of keep-alive connections to maintain in the pool",
        validation_alias="HTTP_MAX_KEEPALIVE_CONNECTIONS",
    )
    keepalive_expiry: float = Field(
        default=5.0,
        description="Time in seconds before an idle keep-alive connection is closed",
        validation_alias="HTTP_KEEPALIVE_EXPIRY",
    )

    model_config = SettingsConfigDict(extra="ignore")


@functools.lru_cache
def get_http_client_settings() -> HTTPClientSettings:
    """Returns a cached instance of the HTTP client settings."""
    return HTTPClientSettings()
