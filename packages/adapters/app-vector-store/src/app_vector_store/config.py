from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class QdrantSettings(BaseSettings):
    """Explicit storage mode; no implicit ephemeral database or global settings cache."""

    model_config = SettingsConfigDict(env_prefix="VECTOR_DB_", extra="ignore")

    mode: Literal["local", "remote", "memory"]
    path: Path | None = None
    url: str | None = None
    api_key: SecretStr | None = None
    timeout: int = Field(default=10, gt=0)

    @model_validator(mode="after")
    def validate_location(self) -> Self:
        if self.mode == "local":
            if self.path is None or self.url is not None or self.api_key is not None:
                raise ValueError("local mode requires path and forbids url/api_key")
        elif self.mode == "remote":
            if not self.url or not self.url.startswith(("http://", "https://")) or self.path is not None:
                raise ValueError("remote mode requires an http(s) URL and forbids path")
        elif self.path is not None or self.url is not None or self.api_key is not None:
            raise ValueError("memory mode forbids path/url/api_key")
        return self
