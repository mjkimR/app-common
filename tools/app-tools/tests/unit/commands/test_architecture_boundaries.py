"""Consumer boundaries must work without package or filename conventions."""

import json
from pathlib import Path

import pytest
from app_tools.commands.check_arch import check_arch, scan_directory
from click.testing import CliRunner

CONFIG = """
[project]
name = "consumer"

[[tool.app-tools.architecture.boundaries]]
name = "application"
source = "consumer.features"
forbidden_imports = ["consumer.server", "sqlalchemy"]
"""


def project(root: Path, source: str, module: str = "src/consumer/features/documents.py") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(CONFIG)
    path = root / module
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    return path


@pytest.mark.parametrize(
    "source",
    [
        "import consumer.server.app as app",
        "from consumer.server import app",
        "from consumer import server",
        "from ..server import app",
        "from .. import server",
        "from sqlalchemy import select",
        "from consumer.server import *",
        "def run():\n    import consumer.server",
    ],
)
def test_forbidden_import_forms(tmp_path, source):
    path = project(tmp_path, source)
    violations = scan_directory([path])
    assert len(violations) == 1
    assert violations[0].rule == "ARCH_FORBIDDEN_IMPORT"
    assert "application" in violations[0].message


@pytest.mark.parametrize(
    "module",
    [
        "src/consumer/features/__init__.py",
        "consumer/features/__init__.py",
        "src/consumer/features/nested/commands.py",
    ],
)
def test_package_relative_imports_and_layouts(tmp_path, module):
    source = "from ..server import app" if module.endswith("__init__.py") else "from ...server import app"
    assert scan_directory([project(tmp_path, source, module)])[0].rule == "ARCH_FORBIDDEN_IMPORT"


@pytest.mark.parametrize(
    ("module", "source"),
    [
        ("src/consumer/features/docs.py", "from consumer.server_utils import app"),
        ("src/consumer/features/docs.py", "from consumer.store import Store"),
        ("src/consumer/features_extra/docs.py", "from consumer.server import app"),
        ("src/consumer/server/app.py", "import sqlalchemy"),
    ],
)
def test_allowed_imports_and_component_prefixes(tmp_path, module, source):
    assert scan_directory([project(tmp_path, source, module)]) == []


def test_nearest_project_and_repository_boundary(tmp_path):
    project(tmp_path, "")
    nested = project(tmp_path / "child", "from consumer.server import app")
    (tmp_path / "child/pyproject.toml").write_text('[project]\nname = "child"\n')
    assert scan_directory([nested]) == []
    (tmp_path / "child/pyproject.toml").unlink()
    (tmp_path / "child/.git").mkdir()
    assert scan_directory([nested]) == []


@pytest.mark.parametrize(
    "config",
    [
        "[broken",
        '[tool.app-tools]\narchitecture = "bad"',
        '[tool.app-tools.architecture]\nboundaries = "bad"',
        CONFIG.replace('source = "consumer.features"', 'source = "consumer.*"'),
        CONFIG.replace('forbidden_imports = ["consumer.server", "sqlalchemy"]', "forbidden_imports = []"),
        CONFIG.replace('name = "application"', 'name = ""'),
        CONFIG.replace('source = "consumer.features"', 'source = "consumer.features"\nunknown = true'),
        CONFIG + CONFIG[CONFIG.index("[[tool.app-tools") :],
    ],
)
def test_invalid_config_fails_once_even_without_python_files(tmp_path, config):
    (tmp_path / "pyproject.toml").write_text(config)
    result = CliRunner().invoke(check_arch, [str(tmp_path), str(tmp_path), "--json"])
    assert result.exit_code == 1
    report = json.loads(result.output)
    assert report["errors_count"] == 1
    assert report["violations"][0]["rule"] == "ARCH_CONFIG_ERROR"


def test_json_exit_status_and_suppression(tmp_path):
    path = project(tmp_path, "from consumer.server import app\n")
    result = CliRunner().invoke(check_arch, [str(path), "--json"])
    assert result.exit_code == 1
    assert json.loads(result.output)["violations"][0]["line"] == 1
    path.write_text("from consumer.server import app  # arch: ignore[ARCH_FORBIDDEN_IMPORT] -- legacy boundary\n")
    assert scan_directory([path]) == []
    path.write_text("from consumer.store import Store  # arch: ignore[ARCH_FORBIDDEN_IMPORT] -- legacy boundary\n")
    assert scan_directory([path])[0].rule == "ARCH_INVALID_SUPPRESSION"
