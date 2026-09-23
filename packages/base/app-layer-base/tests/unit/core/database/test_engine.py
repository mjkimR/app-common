import pytest
from app_layer_base.config import AppSettings
from app_layer_base.core.database.engine import engine_options
from sqlalchemy.ext.asyncio import create_async_engine

SERVER_URL = "postgresql+psycopg://user:pass@db.example.com:5432/app"


def test_server_databases_default_to_sqlalchemy_pool_limits():
    assert engine_options(AppSettings(DATABASE_URL=SERVER_URL)) == {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 10,
    }


def test_pool_limits_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("DB_POOL_SIZE", "2")
    monkeypatch.setenv("DB_MAX_OVERFLOW", "0")
    options = engine_options(AppSettings(DATABASE_URL=SERVER_URL))

    engine = create_async_engine(SERVER_URL, **options)
    assert (engine.pool.size(), engine.pool._max_overflow) == (2, 0)  # type: ignore[attr-defined]


def test_sqlite_is_not_given_pool_limits():
    options = engine_options(AppSettings(DATABASE_URL="sqlite+aiosqlite:///./app.db", DB_POOL_SIZE=2))

    assert options == {"pool_pre_ping": True}
    create_async_engine("sqlite+aiosqlite:///./app.db", **options)


@pytest.mark.parametrize("field, value", [("DB_POOL_SIZE", 0), ("DB_MAX_OVERFLOW", -1)])
def test_pool_limits_are_validated(field, value):
    with pytest.raises(ValueError):
        AppSettings(DATABASE_URL=SERVER_URL, **{field: value})
