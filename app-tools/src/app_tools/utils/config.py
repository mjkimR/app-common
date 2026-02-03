import os


def get_app_home_dir():
    try:
        from app_base.config import get_project_root

        return get_project_root()
    except ImportError:
        return os.getcwd()
