"""One database fixture plugin for all authentication features."""

import logging

pytest_plugins = ["app_testing_base.plugin"]
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
