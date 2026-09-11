from pathlib import Path

import app_layer_base.config_util as util
import pytest


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


def test_get_project_root_infers_from_git(monkeypatch, tmp_path):
    # APP_HOME and get_env_file_path are mocked to ensure fallback to git root check.
    monkeypatch.delenv("APP_HOME", raising=False)
    monkeypatch.setattr(util, "get_env_file_path", lambda: None)

    # Create mock folder structure: tmp_path/.git, and run from tmp_path/sub/dir
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    sub_dir = tmp_path / "sub" / "dir"
    sub_dir.mkdir(parents=True)

    monkeypatch.setattr(Path, "cwd", lambda: sub_dir)
    util.get_project_root.cache_clear()
    assert util.get_project_root() == str(tmp_path)


def test_get_project_root_raises_error_if_not_found(monkeypatch, tmp_path):
    monkeypatch.delenv("APP_HOME", raising=False)
    monkeypatch.setattr(util, "get_env_file_path", lambda: None)

    # Run from directory without .git in its hierarchy
    monkeypatch.setattr(Path, "cwd", lambda: tmp_path)
    util.get_project_root.cache_clear()

    with pytest.raises(RuntimeError, match="Cannot determine project root"):
        util.get_project_root()
