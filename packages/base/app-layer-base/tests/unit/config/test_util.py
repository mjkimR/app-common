import os
import sys
import types
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


def test_load_json_env_expands_values_without_overwriting_explicit_env(monkeypatch):
    monkeypatch.setenv("APP_SECRETS_JSON", '{"DATABASE_URL":"postgres://bundled","NEW_KEY":"value"}')
    monkeypatch.setenv("DATABASE_URL", "postgres://explicit")

    util.load_json_env()

    assert os.environ["DATABASE_URL"] == "postgres://explicit"
    assert os.environ["NEW_KEY"] == "value"


def test_load_json_env_rejects_invalid_payload(monkeypatch):
    monkeypatch.setenv("APP_SECRETS_JSON", "not-json")

    with pytest.raises(RuntimeError, match="valid JSON object"):
        util.load_json_env()


def test_resolve_secret_references_uses_secret_manager(monkeypatch):
    class Payload:
        data = b'{"DATABASE_URL":"postgres://secret"}'

    class Client:
        def secret_version_path(self, project, secret, version):
            assert (project, secret, version) == ("demo", "bundle", "latest")
            return "projects/demo/secrets/bundle/versions/latest"

        def access_secret_version(self, request):
            assert request["name"].endswith("versions/latest")
            return type("Response", (), {"payload": Payload()})()

    monkeypatch.setenv("GCP_PROJECT_ID", "demo")
    monkeypatch.setenv("APP_SECRETS_JSON", "secretref://bundle/latest")
    secretmanager = types.ModuleType("google.cloud.secretmanager")
    secretmanager.SecretManagerServiceClient = Client
    google_cloud = types.ModuleType("google.cloud")
    google_cloud.secretmanager = secretmanager
    google = types.ModuleType("google")
    google.cloud = google_cloud
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", google_cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.secretmanager", secretmanager)

    util.resolve_secret_references()

    assert __import__("os").environ["APP_SECRETS_JSON"] == '{"DATABASE_URL":"postgres://secret"}'


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
