"""Root pytest configuration for app-prebuilt-user.

Database fixtures come from `app_testing_base.plugin`; see that module for
`--db-type`, the `real_commit` marker, and the fixtures it provides.
"""

import logging

pytest_plugins = ["app_testing_base.plugin"]

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
