import functools
import os.path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_base.config.util import get_env_file_path, get_project_root


class AppSettings(BaseSettings):
    DATABASE_URL: str = Field(
        default_factory=lambda: f"sqlite+aiosqlite:///{get_project_root()}/.test.db",
        description="SQLAlchemy async database connection URL (defaults to SQLite)",
    )

    LOG_PATH: str = Field(
        default_factory=lambda: os.path.join(get_project_root(), "logs/app.log"),
        description="Absolute path to the log file",
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
        default_factory=lambda: ["app_base"],
        description="List of module name prefixes included in simplified tracebacks",
    )

    CORS_ALLOWED_ORIGINS: list[str] = Field(default_factory=list, description="Explicit list of allowed CORS origins")
    CORS_ALLOW_ORIGIN_REGEX: str | None = Field(default=None, description="Regex pattern matching allowed CORS origins")
    CORS_ALLOW_CREDENTIALS: bool = Field(
        default=False, description="Allow cookies and credentials to be included in CORS requests"
    )

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        extra="ignore",
    )


@functools.lru_cache
def get_app_settings():
    return AppSettings(**{})
