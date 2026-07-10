"""Test support shipped with app-layer-base.

Anything building on app-layer-base -- the packages in this workspace and any
downstream application -- needs the same handful of things to test against it: a
database session wired to the app's engine accessors, a way to wipe tables between
tests, and a resolver for its `Annotated[T, Depends()]` dependency trees. Those live
here rather than in each repo's `tests/` directory, because a `tests/` directory
shared over `sys.path` is not a package: it collides on the name `tests` and silently
shadows whichever copy loads first.

Install the extra to use this module::

    pip install "app-layer-base[testing]"

The pytest fixtures are a plugin -- pytest never imports this package to find them,
so importing ``app_layer_base.testing`` does not pull in pytest. Enable them from the
top-level ``conftest.py`` of a package's test suite::

    pytest_plugins = ["app_layer_base.testing.db"]

That provides ``--db-type {sqlite,postgres}``, the ``real_commit`` marker, and the
``session`` / ``session_maker`` / ``async_engine`` / ``is_postgres`` fixtures.
"""

from app_layer_base.testing.cleanup import clean_db_after_test
from app_layer_base.testing.fastapi import MockRequest, resolve_dependency
from app_layer_base.testing.helpers import random_email, random_string

__all__ = [
    "MockRequest",
    "clean_db_after_test",
    "random_email",
    "random_string",
    "resolve_dependency",
]
