"""Pytest plugin providing all core testing fixtures and configurations."""

from app_testing_base.client.fixtures import (
    app as app,
)
from app_testing_base.client.fixtures import (
    client_fixture as client,
)
from app_testing_base.client.fixtures import (
    client_headers as client_headers,
)
from app_testing_base.db.fixtures import (
    async_engine as async_engine,
)
from app_testing_base.db.fixtures import (
    db_type as db_type,
)
from app_testing_base.db.fixtures import (
    db_url as db_url,
)
from app_testing_base.db.fixtures import (
    is_postgres as is_postgres,
)
from app_testing_base.db.fixtures import (
    pytest_addoption as pytest_addoption,
)
from app_testing_base.db.fixtures import (
    pytest_configure as pytest_configure,
)
from app_testing_base.db.fixtures import (
    session_fixture as session,
)
from app_testing_base.db.fixtures import (
    session_maker as session_maker,
)
from app_testing_base.db.fixtures import (
    setup_database as setup_database,
)

__all__ = [
    "app",
    "async_engine",
    "client",
    "client_headers",
    "db_type",
    "db_url",
    "is_postgres",
    "pytest_addoption",
    "pytest_configure",
    "session",
    "session_maker",
    "setup_database",
]
