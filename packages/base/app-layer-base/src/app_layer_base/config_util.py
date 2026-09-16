import json
import os
import re
from functools import lru_cache
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

APP_SECRETS_JSON_ENV = "APP_SECRETS_JSON"
_ENV_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_SECRET_REF_PATTERN = re.compile(r"^secretref://([^/]+)/([^/]+)$")


def get_env_filename() -> str:
    """Get the name of the appropriate .env file based on ENV variable"""
    env = os.getenv("ENV")
    return f".env.{env}" if env else ".env"


@lru_cache
def get_env_file_path() -> Path | None:
    """Get the path to the appropriate .env file based on ENV variable"""
    env_file = get_env_filename()
    env_path = find_dotenv(env_file, usecwd=True)
    if env_path:
        return Path(env_path)
    else:
        return None


@lru_cache
def get_project_root() -> str:
    """Get the project home directory from APP_HOME env variable, .env file location, or .git root"""
    root = os.environ.get("APP_HOME")
    if root:
        return root

    env_path = get_env_file_path()
    if env_path:
        # If .env file is found, return its directory as project root
        return os.path.dirname(env_path)

    # Check for .git directory
    current_path = Path.cwd()
    for parent in (current_path, *current_path.parents):
        if (parent / ".git").exists():
            return str(parent)

    # If neither is found, raise an error
    raise RuntimeError(
        "Cannot determine project root. Please set APP_HOME environment variable, ensure .env file exists, or run from a git repository."
    )


def load_env():
    """Load the local .env, resolve secret references, and expand JSON secrets."""
    path = get_env_file_path()
    if path and os.path.exists(path):
        load_dotenv(path)
    resolve_secret_references()
    load_json_env()


def resolve_secret_references() -> None:
    """Resolve ``secretref://SECRET/VERSION`` values without writing them to disk.

    Cloud Run normally injects the real value before the process starts, so this
    path is primarily for running a checked-in ``.env.prod`` locally.
    """
    project = os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT_ID")
    for key, value in list(os.environ.items()):
        match = _SECRET_REF_PATTERN.fullmatch(value)
        if not match:
            continue
        if not project:
            raise RuntimeError(f"{key} uses secretref:// but GOOGLE_CLOUD_PROJECT is not set")
        try:
            from google.cloud import secretmanager
        except ImportError as exc:
            raise RuntimeError("google-cloud-secret-manager is required to resolve secretref:// values") from exc
        client = secretmanager.SecretManagerServiceClient()
        name = client.secret_version_path(project, match.group(1), match.group(2))
        response = client.access_secret_version(request={"name": name})
        os.environ[key] = response.payload.data.decode("utf-8")


def load_json_env(env_var: str = APP_SECRETS_JSON_ENV) -> None:
    """Expand a JSON object from *env_var* into individual environment variables.

    Existing variables win, so a developer or deployment can override one bundled
    value without changing the bundle. Only string values and conventional
    uppercase environment-variable names are accepted.
    """
    raw = os.environ.get(env_var)
    if not raw:
        return

    try:
        values = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"{env_var} must contain a valid JSON object") from exc

    if not isinstance(values, dict) or any(not isinstance(key, str) for key in values):
        raise RuntimeError(f"{env_var} must contain a JSON object")

    for key, value in values.items():
        if not _ENV_KEY_PATTERN.fullmatch(key):
            raise RuntimeError(f"{env_var} contains invalid environment variable name: {key!r}")
        if not isinstance(value, str):
            raise RuntimeError(f"{env_var}.{key} must be a string")
        os.environ.setdefault(key, value)
