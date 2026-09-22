"""Explicit transaction owners must not initialize unrelated app settings or logging."""

import subprocess
import sys


def test_import_does_not_configure_global_logger_or_settings():
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from loguru import logger
import app_layer_base.config as config

def forbidden():
    raise AssertionError("explicit transaction owners do not need global app settings")

config.get_app_settings = forbidden
messages = []
sink = logger.add(lambda message: messages.append(str(message)), format="{message}")
from app_layer_base.core.database.transaction import AsyncTransaction
assert "app_layer_base.core.log" not in sys.modules
logger.info("existing sink")
assert messages == ["existing sink\\n"]
logger.remove(sink)
""",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
