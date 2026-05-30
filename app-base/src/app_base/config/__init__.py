from __future__ import annotations

from typing import TYPE_CHECKING

from app_layer_base.config_util import (
    get_env_filename,
    get_project_root,
)

if TYPE_CHECKING:
    from app_event_broker.config import EventBrokerSettings, get_event_broker_settings
    from app_file_storage.config import FileStorageSettings, get_file_storage_settings
    from app_http_client.config import HTTPClientSettings, get_http_client_settings
    from app_layer_base.config import AppSettings, get_app_settings
    from app_nosql_db.config import NoSQLDBSettings, get_nosql_db_settings
    from app_vector_store.config import VectorDBSettings, get_vector_db_settings

    from .auth import AuthSettings, get_auth_settings

__all__ = [
    "AppSettings",
    "AuthSettings",
    "EventBrokerSettings",
    "FileStorageSettings",
    "HTTPClientSettings",
    "NoSQLDBSettings",
    "VectorDBSettings",
    "get_app_settings",
    "get_auth_settings",
    "get_env_filename",
    "get_event_broker_settings",
    "get_file_storage_settings",
    "get_http_client_settings",
    "get_nosql_db_settings",
    "get_project_root",
    "get_vector_db_settings",
]

_lazy_imports: dict[str, tuple[str, str]] = {
    "AppSettings": ("app_layer_base.config", "AppSettings"),
    "get_app_settings": ("app_layer_base.config", "get_app_settings"),
    "AuthSettings": (".auth", "AuthSettings"),
    "get_auth_settings": (".auth", "get_auth_settings"),
    "VectorDBSettings": ("app_vector_store.config", "VectorDBSettings"),
    "get_vector_db_settings": ("app_vector_store.config", "get_vector_db_settings"),
    "FileStorageSettings": ("app_file_storage.config", "FileStorageSettings"),
    "get_file_storage_settings": ("app_file_storage.config", "get_file_storage_settings"),
    "NoSQLDBSettings": ("app_nosql_db.config", "NoSQLDBSettings"),
    "get_nosql_db_settings": ("app_nosql_db.config", "get_nosql_db_settings"),
    "EventBrokerSettings": ("app_event_broker.config", "EventBrokerSettings"),
    "get_event_broker_settings": ("app_event_broker.config", "get_event_broker_settings"),
    "HTTPClientSettings": ("app_http_client.config", "HTTPClientSettings"),
    "get_http_client_settings": ("app_http_client.config", "get_http_client_settings"),
}


def __getattr__(name: str):
    if name in _lazy_imports:
        import importlib

        module_path, attr_name = _lazy_imports[name]
        if module_path.startswith("."):
            module = importlib.import_module(module_path, package=__name__)
        else:
            module = importlib.import_module(module_path)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
