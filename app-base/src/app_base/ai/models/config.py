import os
import re
from typing import Any

import yaml

from app_base.core.log import logger


class ConfigLoader:
    ENV_PATTERN = re.compile(r"\$\{(\w+)(?::-(.*?))?\}")

    @staticmethod
    def load_yaml_with_env(path: str) -> dict[str, Any]:
        """Load a YAML file and substitute ${ENV_VAR} or ${ENV_VAR:-default} placeholders."""
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found: {path}")

        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        return ConfigLoader._substitute_env(loaded or {})

    @staticmethod
    def _substitute_env(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: ConfigLoader._substitute_env(item) for key, item in value.items()}
        if isinstance(value, list):
            return [ConfigLoader._substitute_env(item) for item in value]
        if isinstance(value, str):
            return ConfigLoader._substitute_env_string(value)
        return value

    @staticmethod
    def _substitute_env_string(value: str) -> str:
        def replace_env(match: re.Match[str]) -> str:
            env_var = match.group(1)
            default_value = match.group(2)
            env_value = os.environ.get(env_var)

            if env_value is not None:
                return env_value
            if default_value is not None:
                return default_value

            logger.error(f"Environment variable '{env_var}' is required by config but is not set.")
            raise ValueError("Required infrastructure configuration key is missing from the environment.")

        return ConfigLoader.ENV_PATTERN.sub(replace_env, value)
