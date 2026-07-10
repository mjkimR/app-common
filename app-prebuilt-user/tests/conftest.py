"""Root pytest configuration for app-prebuilt-user.

Database fixtures come from `app_layer_base.testing.db`; see that module for
`--db-type`, the `real_commit` marker, and the fixtures it provides.
"""

import logging

pytest_plugins = ["app_layer_base.testing.db"]

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
