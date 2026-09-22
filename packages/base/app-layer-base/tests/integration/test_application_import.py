import subprocess
import sys
import textwrap


def test_application_import_does_not_load_database_transport_or_settings():
    source = textwrap.dedent("""
        import sys
        import app_layer_base.config as config

        def forbidden():
            raise AssertionError("application import read global settings")

        config.get_app_settings = forbidden
        from app_layer_base.application import Command, TransactionScope, execute_command

        for name in sys.modules:
            assert not name.startswith(("sqlalchemy", "fastapi", "app_layer_base.core.database", "app_layer_base.core.log")), name
    """)
    result = subprocess.run([sys.executable, "-c", source], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
