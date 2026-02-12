import os
import sys
from typing import Any, Dict, Type

import click

# Assume app_base is installed and importable
try:
    from app_base.config.auth import AuthSettings
    from app_base.config.config import AppSettings
    from app_base.config.event_broker import (
        EventBrokerSettings,
    )
    from app_base.config.file_storage import (
        FileStorageSettings,
    )
    from app_base.config.util import get_env_file_path  # This is important for the _env_file parameter
    from app_base.config.vector_db import (
        VectorDBSettings,
    )
except ImportError:
    print(
        "Error: Could not import 'app_base.config' modules. Please ensure 'app-base' is installed (e.g., 'pip install app-base') in your Python environment.",
        file=sys.stderr,
    )
    sys.exit(1)


def get_env_variable_specs(settings_class: Type[Any], provider_type: str | None = None) -> Dict[str, str]:
    """
    Extracts environment variable specifications from a Pydantic BaseSettings class.
    Handles aliases, env_prefix, and nested delimiters.
    """
    specs = {}

    # Temporarily load .env file path to pass to settings, as it's required by Pydantic_settings
    # For external usage, get_env_file_path() would typically resolve based on current working directory
    # or an explicit ENV variable. This is fine.
    env_file_path = get_env_file_path()

    if provider_type:
        main_provider_env_var = None
        for field_name, field_info in settings_class.model_fields.items():
            if field_name == "provider" and field_info.alias:
                main_provider_env_var = field_info.alias
                break

        if main_provider_env_var:
            original_provider_value = os.getenv(main_provider_env_var)
            os.environ[main_provider_env_var] = provider_type

            specs[main_provider_env_var] = (
                f"Type: str. Default: '{provider_type}' (Controls which sub-configuration is active)."
            )

            try:
                main_settings_instance = settings_class(_env_file=env_file_path)
            except Exception as e:
                print(
                    f"Error instantiating main settings class {settings_class.__name__} for provider {provider_type}: {e}",
                    file=sys.stderr,
                )
                if original_provider_value is not None:
                    os.environ[main_provider_env_var] = original_provider_value
                else:
                    del os.environ[main_provider_env_var]
                return specs

            nested_config_instance = main_settings_instance.config

            config_model_config = nested_config_instance.model_config
            env_prefix = config_model_config.get("env_prefix", "")

            for field_name, field_info in nested_config_instance.model_fields.items():
                env_var_name = field_info.alias or field_name.upper()
                full_env_var = f"{env_prefix}{env_var_name}"

                field_type = (
                    field_info.annotation.__name__
                    if hasattr(field_info.annotation, "__name__")
                    else str(field_info.annotation)
                )
                default_value = "'<hidden>'" if field_type == "SecretStr" else repr(field_info.default)
                specs[full_env_var] = f"Type: {field_type}. Default: {default_value}"

            if original_provider_value is not None:
                os.environ[main_provider_env_var] = original_provider_value
            else:
                del os.environ[main_provider_env_var]

        else:
            print(
                f"Warning: Could not find main provider alias for {settings_class.__name__}. Skipping nested config inspection.",
                file=sys.stderr,
            )

    else:
        try:
            settings_instance = settings_class(_env_file=env_file_path)
        except Exception as e:
            print(f"Error instantiating settings class {settings_class.__name__}: {e}", file=sys.stderr)
            return specs

        config_model_config = settings_instance.model_config
        env_prefix = config_model_config.get("env_prefix", "")

        for field_name, field_info in settings_instance.model_fields.items():
            env_var_name = field_info.alias or field_name.upper()
            full_env_var = f"{env_prefix}{env_var_name}"

            field_type = (
                field_info.annotation.__name__
                if hasattr(field_info.annotation, "__name__")
                else str(field_info.annotation)
            )
            default_value = "'<hidden>'" if field_type == "SecretStr" else repr(field_info.default)
            specs[full_env_var] = f"Type: {field_type}. Default: {default_value}"

    return specs


@click.command(name="get-env-spec")
@click.option(
    "--type",
    required=True,
    type=click.Choice(
        [
            "auth",
            "app",
            "file_storage",
            "file_storage_none",
            "file_storage_local",
            "file_storage_s3",
            "event_broker",
            "event_broker_none",
            "event_broker_in_memory",
            "event_broker_rabbitmq",
            "event_broker_redis",
            "vector_db",
            "vector_db_none",
            "vector_db_qdrant",
            "vector_db_milvus",
        ]
    ),
    help="The type of configuration to inspect (e.g., auth, file_storage_s3).",
)
def get_env_spec(type: str):
    """List environment variable specifications for app-base configurations."""
    settings_map = {
        "auth": (AuthSettings, None),
        "app": (AppSettings, None),
        "file_storage": (FileStorageSettings, None),
        "file_storage_none": (FileStorageSettings, "none"),
        "file_storage_local": (FileStorageSettings, "local"),
        "file_storage_s3": (FileStorageSettings, "s3"),
        "event_broker": (EventBrokerSettings, None),
        "event_broker_none": (EventBrokerSettings, "none"),
        "event_broker_in_memory": (EventBrokerSettings, "in_memory"),
        "event_broker_rabbitmq": (EventBrokerSettings, "rabbitmq"),
        "event_broker_redis": (EventBrokerSettings, "redis"),
        "vector_db": (VectorDBSettings, None),
        "vector_db_none": (VectorDBSettings, "none"),
        "vector_db_qdrant": (VectorDBSettings, "qdrant"),
        "vector_db_milvus": (VectorDBSettings, "milvus"),
    }

    settings_class, provider_type = settings_map.get(type, (None, None))
    if not settings_class:
        click.echo(f"Unknown settings type: {type}", err=True)
        sys.exit(1)

    click.echo(f"--- Environment Variables for {type.replace('_', ' ').title()} ---")
    specs = get_env_variable_specs(settings_class, provider_type)

    if specs:
        # Sort specs alphabetically by environment variable name for consistent output
        for env_var, description in sorted(specs.items()):
            click.echo(f"{env_var}: {description}")
    else:
        click.echo("No environment variables found or an error occurred.", err=True)
