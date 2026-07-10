"""Root pytest configuration for app-layer-base.

The database fixtures live in the library itself (`app_layer_base.testing.db`) so that
every package in this workspace -- and every downstream consumer -- shares one copy.
See that module for `--db-type`, the `real_commit` marker, and the fixtures it provides.

Test structure:
    tests/
    ├── conftest.py   <- you are here
    ├── unit/         <- mocked, no database
    └── integrate/    <- real database
"""

import logging

# Fixtures arrive as a pytest plugin rather than a `sys.path` import, so nothing named
# `tests` needs to be importable and no other package's `tests/` can shadow this one.
pytest_plugins = ["app_layer_base.testing.db"]

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
