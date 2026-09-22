from functools import lru_cache

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ApiKeySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_API_KEY_", extra="ignore", hide_input_in_errors=True)
    root_key: SecretStr | None = None

    @field_validator("root_key")
    @classmethod
    def validate_root(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None or not value.get_secret_value():
            return None
        if len(value.get_secret_value()) < 32:
            raise ValueError("Root API keys must contain at least 32 characters")
        return value


@lru_cache
def get_api_key_settings() -> ApiKeySettings:
    return ApiKeySettings()
