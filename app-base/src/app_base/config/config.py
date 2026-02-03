import functools
import os.path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app_base.config.util import get_env_file_path, get_project_root


class AppSettings(BaseSettings):
    DATABASE_URL: str = Field(default=f"sqlite+aiosqlite:///{get_project_root()}/.test.db")

    LOG_PATH: str = Field(default=os.path.join(get_project_root(), "logs/app.log"))
    LOG_JSON_FORMAT: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")

    model_config = SettingsConfigDict(
        env_file=get_env_file_path(),
        extra="ignore",
    )


@functools.lru_cache
def get_app_settings():
    return AppSettings(**{})
