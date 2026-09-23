from functools import lru_cache
from typing import Literal
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GoogleAuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GOOGLE_AUTH_", extra="ignore")
    enabled: bool = False
    client_id: str = ""
    client_secret: SecretStr = SecretStr("")
    redirect_uri: str = ""
    frontend_url: str = ""
    response_mode: Literal["query", "form_post"] = "query"
    cookie_secure: bool = True
    cookie_path: str = "/api/v1/auth/google"

    @model_validator(mode="after")
    def validate_configuration(self) -> "GoogleAuthSettings":
        if not self.enabled:
            return self
        if not self.client_id or not self.client_secret.get_secret_value():
            raise ValueError("Google OAuth client credentials are required")
        for value in (self.redirect_uri, self.frontend_url):
            url = urlsplit(value)
            local = url.hostname in {"localhost", "127.0.0.1"}
            if not url.netloc or url.username or url.password or url.query or url.fragment:
                raise ValueError("Configure absolute callback/frontend URLs without query or fragment")
            if url.scheme != "https" and not (url.scheme == "http" and local and not self.cookie_secure):
                raise ValueError("OAuth URLs require HTTPS (HTTP is allowed only for local development)")
        callback, frontend = urlsplit(self.redirect_uri), urlsplit(self.frontend_url)
        if self.response_mode == "form_post" and (not self.cookie_secure or callback.scheme != "https"):
            raise ValueError("form_post requires HTTPS and secure cookies")
        if (callback.scheme, callback.netloc) != (frontend.scheme, frontend.netloc):
            raise ValueError("Callback and frontend must share an origin; use the frontend API proxy locally")
        if not self.cookie_path.startswith("/") or not callback.path.startswith(self.cookie_path + "/"):
            raise ValueError("Cookie path must cover the callback route")
        if not self.cookie_secure and callback.scheme == "https":
            raise ValueError("HTTPS deployments require secure cookies")
        return self


@lru_cache
def get_google_auth_settings() -> GoogleAuthSettings:
    return GoogleAuthSettings()
