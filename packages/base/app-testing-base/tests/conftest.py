"""Root test configuration for app-testing-base tests."""

import logging

pytest_plugins = ["app_testing_base.plugin"]

logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
