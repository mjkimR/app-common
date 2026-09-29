from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class BrowserAuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="BROWSER_AUTH_")

    cookie_name: str = "app_refresh"
    cookie_path: str = "/api/v1/auth"
    # None allows plain HTTP only on loopback development hosts.
    cookie_secure: bool | None = None
    allowed_origins: list[str] = []


@lru_cache
def get_browser_auth_settings() -> BrowserAuthSettings:
    return BrowserAuthSettings()
