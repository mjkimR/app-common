import os

import app_base.config.util as util


def test_get_env_filename_default_when_env_missing(monkeypatch):
    # When ENV isn't set, default .env should be used.
    monkeypatch.delenv("ENV", raising=False)
    assert util.get_env_filename() == ".env"


def test_get_env_filename_uses_env_suffix(monkeypatch):
    # When ENV is set, .env.<ENV> should be used.
    monkeypatch.setenv("ENV", "prod")
    assert util.get_env_filename() == ".env.prod"


def test_get_project_root_prefers_app_home(monkeypatch):
    # APP_HOME should override any inferred root.
    monkeypatch.setenv("APP_HOME", "/tmp/app_home")
    util.get_project_root.cache_clear()
    assert util.get_project_root() == "/tmp/app_home"


def test_get_project_root_falls_back_to_cwd(monkeypatch):
    # When no APP_HOME and no env file, use current working directory.
    monkeypatch.delenv("APP_HOME", raising=False)

    # Force get_env_file_path() to return None.
    monkeypatch.setattr(util, "get_env_file_path", lambda: None)
    util.get_project_root.cache_clear()

    monkeypatch.setattr(os, "getcwd", lambda: "/tmp/cwd")
    assert util.get_project_root() == "/tmp/cwd"
