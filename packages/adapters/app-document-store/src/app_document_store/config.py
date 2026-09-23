from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def validate_segment(value: str) -> str:
    """Require one literal Firestore path segment, never an arbitrary path."""
    if (
        not value.strip()
        or value in (".", "..")
        or "/" in value
        or (value.startswith("__") and value.endswith("__"))
        or len(value.encode("utf-8")) > 1500
    ):
        raise ValueError("Expected a nonempty Firestore ID without '/', '.', '..', or reserved __name__ syntax")
    return value


class FirestoreSettings(BaseSettings):
    """Explicit project and app namespace; no global settings cache or implicit DB provisioning."""

    model_config = SettingsConfigDict(env_prefix="DOCUMENT_STORE_", extra="ignore")

    project_id: str = Field(min_length=1)
    database_id: str = "(default)"
    namespace: str
    mode: Literal["firestore", "emulator"] = "firestore"
    timeout: float = Field(default=10, gt=0, allow_inf_nan=False)

    _segments = field_validator("project_id", "database_id", "namespace")(validate_segment)
