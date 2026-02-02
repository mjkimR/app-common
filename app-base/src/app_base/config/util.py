import os


def get_app_home():
    """Get the path to the app home directory"""
    return os.environ.get("APP_HOME", os.getcwd())


def get_env_filename():
    runtime_env = os.getenv("ENV")
    home = get_app_home()

    return f"{home}/.env.{runtime_env}" if runtime_env else f"{home}/.env"


def load_env():
    if os.path.exists(get_env_filename()):
        from dotenv import load_dotenv

        load_dotenv(get_env_filename())
