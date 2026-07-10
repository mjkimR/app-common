"""Root pytest configuration for app-prebuilt-outbox.

Database fixtures come from `app_layer_base.testing.db`; see that module for
`--db-type`, the `real_commit` marker, and the fixtures it provides.
"""

import logging

import pytest

# Import models so the Outbox table is registered on Base.metadata before create_all.
from app_prebuilt_outbox import models  # noqa: F401

pytest_plugins = ["app_layer_base.testing.db"]

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Every test here needs real commits, so mark the whole suite `real_commit`.

    An outbox relay is defined by what a *different* connection can see: the worker
    that claims an event is never the one that wrote it. The default savepoint strategy
    binds every session to one connection and rolls back at the end, which would hide
    exactly the behaviour these tests exist to check.
    """
    for item in items:
        item.add_marker(pytest.mark.real_commit)
