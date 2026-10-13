"""``RULE-app-forbidden-import``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

from pathlib import Path

import pytest
from devkit.rules.testing import check, load_rule

RULE = load_rule(__file__)

CONFIG = """
[project]
name = "consumer"

[[tool.app-tools.architecture.boundaries]]
name = "application"
source = "consumer.features"
forbidden_imports = ["consumer.server", "sqlalchemy"]
"""


def project(source: str, module: str = "src/consumer/features/documents.py") -> dict[str, str]:
    return {"pyproject.toml": CONFIG, module: source}


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
def test_forbidden_import_forms(tmp_path: Path, source: str) -> None:
    [violation] = check(RULE, tmp_path, project(source))
    assert "Boundary 'application'" in violation.message and violation.severity.value == "error"


@pytest.mark.parametrize(
    "module",
    ["src/consumer/features/__init__.py", "consumer/features/__init__.py", "src/consumer/features/nested/commands.py"],
)
def test_package_relative_imports_and_layouts(tmp_path: Path, module: str) -> None:
    source = "from ..server import app" if module.endswith("__init__.py") else "from ...server import app"
    assert len(check(RULE, tmp_path, project(source, module))) == 1


@pytest.mark.parametrize(
    ("module", "source"),
    [
        ("src/consumer/features/docs.py", "from consumer.server_utils import app"),
        ("src/consumer/features/docs.py", "from consumer.store import Store"),
        ("src/consumer/features_extra/docs.py", "from consumer.server import app"),
        ("src/consumer/server/app.py", "import sqlalchemy"),
    ],
)
def test_allowed_imports_and_component_prefixes(tmp_path: Path, module: str, source: str) -> None:
    assert check(RULE, tmp_path, project(source, module)) == []


def test_the_nearest_project_and_the_repository_boundary_govern(tmp_path: Path) -> None:
    files = {
        **project(""),
        **{f"child/{name}": text for name, text in project("from consumer.server import app").items()},
    }
    files["child/pyproject.toml"] = '[project]\nname = "child"\n'
    assert check(RULE, tmp_path, files) == []
    (tmp_path / "child/pyproject.toml").unlink()
    (tmp_path / "child/.git").mkdir()
    assert check(RULE, tmp_path) == []


def test_a_reasoned_suppression_hides_the_finding(tmp_path: Path) -> None:
    source = "from consumer.server import app  # arch: ignore[RULE-app-forbidden-import] -- legacy boundary\n"
    assert check(RULE, tmp_path, project(source)) == []
