from app_layer_base.config import AppSettings


def test_app_env_defaults_to_development():
    settings = AppSettings(_env_file=None)

    assert settings.APP_ENV == "development"
    assert settings.is_production is False


def test_app_env_can_be_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    settings = AppSettings(_env_file=None)

    assert settings.APP_ENV == "production"
    assert settings.is_production is True


def test_is_production_when_app_env_is_production():
    settings = AppSettings(APP_ENV="production")

    assert settings.is_production is True


def test_is_production_ignores_case_and_whitespace():
    settings = AppSettings(APP_ENV=" Production ")

    assert settings.is_production is True
