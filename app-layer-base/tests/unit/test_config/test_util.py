import app_layer_base.config_util as util


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
