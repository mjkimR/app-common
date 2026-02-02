import os
import pathlib


def get_repo_path():
    """Get the path to the repository."""
    path = str(pathlib.Path(__file__).parent.parent.parent.parent.resolve())
    return path


def get_app_path():
    """Get the path to the app_base."""
    path = str(pathlib.Path(__file__).parent.parent.parent.resolve())
    return path


def get_env_filename():
    runtime_env = os.getenv("ENV")
    home = get_repo_path()

    return f"{home}/.env.{runtime_env}" if runtime_env else f"{home}/.env"


def load_env():
    if os.path.exists(get_env_filename()):
        from dotenv import load_dotenv

        load_dotenv(get_env_filename())
