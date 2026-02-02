import os
import pathlib


def get_app_path():
    """Get the path to the app_base."""
    if os.getenv("APP_HOME"):
        return str(pathlib.Path(os.getenv("APP_HOME")))
    else:
        return str(os.getcwd)


def get_env_filename():
    runtime_env = os.getenv("ENV")
    home = get_app_path()

    return f"{home}/.env.{runtime_env}" if runtime_env else f"{home}/.env"


def load_env():
    if os.path.exists(get_env_filename()):
        from dotenv import load_dotenv

        load_dotenv(get_env_filename())
