import os
from functools import lru_cache
from pathlib import Path

from dotenv import find_dotenv, load_dotenv


def get_env_filename() -> str:
    """Get the name of the appropriate .env file based on ENV variable"""
    env = os.getenv("ENV")
    return f".env.{env}" if env else ".env"


@lru_cache
def get_env_file_path() -> Path | None:
    """Get the path to the appropriate .env file based on ENV variable"""
    env_file = get_env_filename()
    env_path = find_dotenv(env_file)
    if env_path:
        return Path(env_path)
    else:
        return None


@lru_cache
def get_project_root() -> str:
    """Get the project home directory from APP_HOME env variable or default to .env file location"""
    root = os.environ.get("APP_HOME")
    if root:
        return root

    env_path = get_env_file_path()
    if env_path:
        # If .env file is found, return its directory as project root
        return os.path.dirname(env_path)

    return os.getcwd()


def load_env():
    """Load environment variables from the .env file"""
    path = get_env_file_path()
    if path and os.path.exists(path):
        load_dotenv(path)
