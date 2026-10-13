"""The environment variables app-common settings classes read, without loading any value."""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from typing import Any

from app_tools.errors import invalid_input

# type -> (distribution, settings classes as "module:Class")
SETTINGS: dict[str, tuple[str, tuple[str, ...]]] = {
    "app": ("app-layer-base", ("app_layer_base.config:AppSettings",)),
    "auth": ("app-prebuilt-auth", ("app_prebuilt_auth.user.config.auth:AuthSettings",)),
    "file_storage": ("app-file-storage", ("app_file_storage.config:FileStorageSettings",)),
    "file_storage_local": (
        "app-file-storage",
        ("app_file_storage.config:FileStorageSettings", "app_file_storage.providers.local:LocalFileStorageSettings"),
    ),
    "file_storage_s3": (
        "app-file-storage",
        ("app_file_storage.config:FileStorageSettings", "app_file_storage.providers.s3:S3FileStorageSettings"),
    ),
    "vector_db": ("app-vector-store", ("app_vector_store.config:QdrantSettings",)),
}


@dataclass(frozen=True)
class EnvVariable:
    name: str
    type: str
    default: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "type": self.type, "default": self.default}


def _variables(settings_class: Any) -> list[EnvVariable]:
    prefix = settings_class.model_config.get("env_prefix", "")
    variables = []
    for name, info in settings_class.model_fields.items():
        type_name = getattr(info.annotation, "__name__", None) or str(info.annotation)
        default = "<hidden>" if type_name == "SecretStr" else repr(info.default)
        # pydantic-settings reads an aliased field from its alias alone, without the prefix.
        variables.append(EnvVariable(info.alias or f"{prefix}{name}".upper(), type_name, default))
    return variables


def env_spec(settings_type: str) -> list[EnvVariable]:
    """The variables of one settings type, sorted by name."""
    distribution, targets = SETTINGS[settings_type]
    variables: list[EnvVariable] = []
    for target in targets:
        module_name, class_name = target.split(":")
        try:
            settings_class = getattr(importlib.import_module(module_name), class_name)
        except ImportError as exc:
            raise invalid_input(
                f"'{settings_type}' settings come from {distribution}, which is not installed here.",
                code="APP_ENV_SPEC_PACKAGE_MISSING",
                fix=f"Add {distribution} to the project, or ask for a settings type of an installed package.",
            ) from exc
        variables += _variables(settings_class)
    return sorted(variables, key=lambda variable: variable.name)
