import functools
import warnings

from loguru import logger
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_layer_base.config_util import get_project_root
from app_layer_base.core.environment import (
    is_development_environment,
    is_production_environment,
    is_test_environment,
)

__all__ = ["AppSettings", "get_app_settings", "get_project_root"]


class AppSettings(BaseSettings):
    APP_ENV: str = Field(
        default="development",
        description="Runtime environment name. Set to 'production' to enable production-only behavior.",
    )

    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///:memory:",
        description="SQLAlchemy async database connection URL (defaults to in-memory SQLite)",
    )

    LOG_PATH: str | None = Field(
        default=None,
        description="Absolute path to the log file. If None or empty, file logging is disabled.",
    )
    LOG_JSON_FORMAT: bool = Field(
        default=False, description="Emit logs in JSON format when True (useful for log aggregators)"
    )
    LOG_LEVEL: str = Field(
        default="INFO", description="Minimum log level to emit (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    LOG_SIMPLE_TRACEBACK: bool = Field(
        default=True, description="Shorten tracebacks to only show frames matching the whitelist"
    )
    LOG_TRACEBACK_WHITELIST: list[str] = Field(
        default_factory=lambda: ["app_layer_base"],
        description="List of module name prefixes included in simplified tracebacks",
    )

    CORS_ALLOWED_ORIGINS: list[str] = Field(default_factory=list, description="Explicit list of allowed CORS origins")
    CORS_ALLOW_ORIGIN_REGEX: str | None = Field(default=None, description="Regex pattern matching allowed CORS origins")
    CORS_ALLOW_CREDENTIALS: bool = Field(
        default=False, description="Allow cookies and credentials to be included in CORS requests"
    )

    ERROR_ADVISORY_MODE: str = Field(
        default="auto",
        description="Controls exposure of advisory details in HTTP error responses: 'auto' (non-production), 'always', or 'never'.",
    )

    model_config = SettingsConfigDict(
        extra="ignore",
    )

    @model_validator(mode="after")
    def _check_in_memory_db(self) -> "AppSettings":
        if ":memory:" in self.DATABASE_URL:
            msg = (
                "DATABASE_URL is set to an in-memory SQLite database (':memory:'). "
                "Data will be transient and lost once the application process terminates."
            )
            warnings.warn(msg, UserWarning, stacklevel=2)
            logger.warning(msg)
        return self

    @property
    def is_production(self) -> bool:
        return is_production_environment(self.APP_ENV)

    @property
    def is_development(self) -> bool:
        return is_development_environment(self.APP_ENV)

    @property
    def is_test(self) -> bool:
        return is_test_environment(self.APP_ENV)


@functools.lru_cache
def get_app_settings():
    return AppSettings(**{})
