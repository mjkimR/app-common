import pytest
from app_layer_base.config import AppSettings


def test_app_env_defaults_to_development():
    settings = AppSettings()

    assert settings.APP_ENV == "development"
    assert settings.is_production is False


def test_app_env_can_be_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    settings = AppSettings()

    assert settings.APP_ENV == "production"
    assert settings.is_production is True


def test_is_production_when_app_env_is_production():
    settings = AppSettings(APP_ENV="production")

    assert settings.is_production is True


def test_is_production_ignores_case_and_whitespace():
    settings = AppSettings(APP_ENV=" Production ")

    assert settings.is_production is True


def test_database_url_defaults_to_in_memory():
    with pytest.warns(UserWarning, match=r"DATABASE_URL is set to an in-memory SQLite database"):
        settings = AppSettings()

    assert settings.DATABASE_URL == "sqlite+aiosqlite:///:memory:"


def test_database_url_warning_emitted_when_memory_specified():
    with pytest.warns(UserWarning, match=r"DATABASE_URL is set to an in-memory SQLite database"):
        AppSettings(DATABASE_URL="sqlite+aiosqlite:///:memory:")


def test_database_url_no_warning_for_non_memory(recwarn):
    AppSettings(DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/dbname")
    user_warnings = [w for w in recwarn if issubclass(w.category, UserWarning)]
    assert len(user_warnings) == 0
