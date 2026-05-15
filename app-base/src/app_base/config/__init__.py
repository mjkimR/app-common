from __future__ import annotations

from typing import TYPE_CHECKING

from .util import (
    get_env_filename,
    get_project_root,
)

if TYPE_CHECKING:
    from .auth import AuthSettings, get_auth_settings
    from .config import AppSettings, get_app_settings
    from .event_broker import EventBrokerSettings, get_event_broker_settings
    from .file_storage import FileStorageSettings, get_file_storage_settings
    from .http_client import HTTPClientSettings, get_http_client_settings
    from .nosql_db import NoSQLDBSettings, get_nosql_db_settings
    from .vector_db import VectorDBSettings, get_vector_db_settings

__all__ = [
    # util functions,
    "get_project_root",
    "get_env_filename",
    # settings classes,
    "AppSettings",
    "get_app_settings",
    "AuthSettings",
    "get_auth_settings",
    "VectorDBSettings",
    "get_vector_db_settings",
    "FileStorageSettings",
    "get_file_storage_settings",
    "NoSQLDBSettings",
    "get_nosql_db_settings",
    "EventBrokerSettings",
    "get_event_broker_settings",
    "HTTPClientSettings",
    "get_http_client_settings",
]

_lazy_imports: dict[str, str] = {
    "AppSettings": ".config",
    "get_app_settings": ".config",
    "AuthSettings": ".auth",
    "get_auth_settings": ".auth",
    "VectorDBSettings": ".vector_db",
    "get_vector_db_settings": ".vector_db",
    "FileStorageSettings": ".file_storage",
    "get_file_storage_settings": ".file_storage",
    "NoSQLDBSettings": ".nosql_db",
    "get_nosql_db_settings": ".nosql_db",
    "EventBrokerSettings": ".event_broker",
    "get_event_broker_settings": ".event_broker",
    "HTTPClientSettings": ".http_client",
    "get_http_client_settings": ".http_client",
}


def __getattr__(name: str):
    if name in _lazy_imports:
        import importlib

        module = importlib.import_module(_lazy_imports[name], package=__name__)
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
