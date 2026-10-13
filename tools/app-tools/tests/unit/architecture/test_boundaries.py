"""Consumer boundaries must work without package or filename conventions."""

from pathlib import Path

import pytest

from tests.unit.architecture.support import app_violations, rules_check, scan

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
    violations = scan(path)
    assert len(violations) == 1
    assert violations[0].rule == "RULE-app-forbidden-import"
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
    assert scan(project(tmp_path, source, module))[0].rule == "RULE-app-forbidden-import"


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
    assert scan(project(tmp_path, source, module)) == []


def test_nearest_project_and_repository_boundary(tmp_path):
    project(tmp_path, "")
    nested = project(tmp_path / "child", "from consumer.server import app")
    (tmp_path / "child/pyproject.toml").write_text('[project]\nname = "child"\n')
    assert scan(nested) == []
    (tmp_path / "child/pyproject.toml").unlink()
    (tmp_path / "child/.git").mkdir()
    assert scan(nested) == []


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
    (tmp_path / "module.py").write_text("x = 1\n")
    (tmp_path / "other.py").write_text("y = 2\n")
    exit_code, document = rules_check(tmp_path, tmp_path, tmp_path)
    assert exit_code == 1
    assert [v["rule_id"] for v in app_violations(document)] == ["RULE-app-architecture-config"]


def test_json_exit_status_and_suppression(tmp_path):
    path = project(tmp_path, "from consumer.server import app\n")
    exit_code, document = rules_check(tmp_path, path)
    assert exit_code == 1
    assert [v["line"] for v in app_violations(document)] == [1]
    path.write_text("from consumer.server import app  # arch: ignore[RULE-app-forbidden-import] -- legacy boundary\n")
    assert scan(path) == []
    path.write_text("from consumer.store import Store  # arch: ignore[RULE-app-forbidden-import] -- legacy boundary\n")
    assert scan(path)[0].rule == "RULE-app-invalid-suppression"
