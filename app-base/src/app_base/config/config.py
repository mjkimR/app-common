import functools
import os.path

from pydantic import Field
from pydantic_settings import BaseSettings

from app_base.config.util import get_app_home


class AppSettings(BaseSettings):
    DATABASE_URL: str = Field(default=f"sqlite+aiosqlite:///{get_app_home()}/.test.db")

    LOG_PATH: str = Field(default=os.path.join(get_app_home(), "logs/app.log"))
    LOG_JSON_FORMAT: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")


@functools.lru_cache
def get_app_settings():
    return AppSettings()  # type: ignore



