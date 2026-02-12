import functools
import os.path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_base.config.util import get_env_file_path, get_project_root


class AppSettings(BaseSettings):
    DATABASE_URL: str = Field(default=f"sqlite+aiosqlite:///{get_project_root()}/.test.db")

    LOG_PATH: str = Field(default=os.path.join(get_project_root(), "logs/app.log"))
    LOG_JSON_FORMAT: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")
    LOG_SIMPLE_TRACEBACK: bool = Field(default=True)
    LOG_TRACEBACK_WHITELIST: list[str] = Field(default_factory=lambda: ["app_base"])

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        extra="ignore",
    )

    @field_validator("LOG_TRACEBACK_WHITELIST", mode="before")
    @classmethod
    def parse_list_from_str(cls, v: Any) -> Any:
        if isinstance(v, str):
            if not v.strip():
                return []
            if v.strip().startswith("["):
                return v
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


@functools.lru_cache
def get_app_settings():
    return AppSettings(**{})
