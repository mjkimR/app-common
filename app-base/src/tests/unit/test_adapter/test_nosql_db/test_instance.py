import pytest
from app_base.adapter.nosql_db.instance import (
    close_nosql_db,
    get_nosql_db_provider,
    set_nosql_db_provider,
    setup_nosql_db_provider,
)


def test_set_nosql_db_provider(mock_provider):
    set_nosql_db_provider(mock_provider)
    assert get_nosql_db_provider() == mock_provider


def test_set_nosql_db_provider_already_initialized(mock_provider):
    set_nosql_db_provider(mock_provider)
    with pytest.raises(RuntimeError, match=r"NoSQL DB provider is already initialized."):
        set_nosql_db_provider(mock_provider)


def test_get_nosql_db_provider_not_initialized():
    with pytest.raises(RuntimeError, match=r"NoSQL DB provider is not initialized. Check lifespan."):
        get_nosql_db_provider()


async def test_close_nosql_db(mock_provider):
    set_nosql_db_provider(mock_provider)
    await close_nosql_db()
    assert mock_provider.close_called
    with pytest.raises(RuntimeError):
        get_nosql_db_provider()


async def test_setup_nosql_db_provider_none_provider():
    from unittest.mock import MagicMock

    from app_base.config.nosql_db import NoSQLDBSettings

    settings = MagicMock(spec=NoSQLDBSettings)
    settings.provider = "none"
    # Should not raise, just skips
    await setup_nosql_db_provider(settings)
    with pytest.raises(RuntimeError):
        get_nosql_db_provider()


async def test_setup_nosql_db_provider_already_initialized(mock_provider):
    from unittest.mock import MagicMock

    from app_base.config.nosql_db import NoSQLDBSettings

    set_nosql_db_provider(mock_provider)

    settings = MagicMock(spec=NoSQLDBSettings)
    settings.provider = "some_provider"
    # Already initialized → should log and return without error
    await setup_nosql_db_provider(settings)
    assert get_nosql_db_provider() == mock_provider
