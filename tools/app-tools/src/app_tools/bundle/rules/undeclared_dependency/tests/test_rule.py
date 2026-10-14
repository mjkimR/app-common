"""``RULE-app-undeclared-dependency``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from devkit.rules.testing import check, load_rule

RULE = load_rule(__file__)


def project(dependencies: list[str], name: str = "consumer") -> dict[str, str]:
    """A package manifest; the module under test goes to ``src/consumer/main.py``."""
    return {"pyproject.toml": f'[project]\nname = "{name}"\ndependencies = {json.dumps(dependencies)}\n'}


def test_an_undeclared_app_common_package_warns(tmp_path: Path) -> None:
    [violation] = check(
        RULE, tmp_path, {**project([]), "src/consumer/main.py": "from app_file_storage import provider"}
    )
    assert violation.message == "app-file-storage is imported but not declared by consumer."
    assert violation.severity.value == "warning"


def test_devkit_advisory_must_be_declared_where_it_is_imported(tmp_path: Path) -> None:
    files = {**project(["app-layer-base"]), "src/consumer/main.py": "from devkit.advisory import AdvisoryError"}
    [violation] = check(RULE, tmp_path, files)
    assert violation.message.startswith("devkit-advisory is imported") and "Git source" in violation.remediation
    for declared in ("devkit-advisory>=0.1", "devkit-agt>=0.1"):  # devkit-agt depends on devkit-advisory
        files = {**project(["app-layer-base", declared]), "src/consumer/main.py": "import devkit.advisory"}
        assert check(RULE, tmp_path, files) == []


def test_from_devkit_import_advisory_is_devkit_advisory(tmp_path: Path) -> None:
    files = {**project(["devkit-advisory>=0.1"]), "src/consumer/main.py": "from devkit import advisory"}
    assert check(RULE, tmp_path, files) == []
    files["src/consumer/main.py"] = "from devkit import advisory, cli"
    [violation] = check(RULE, tmp_path, files)
    assert violation.message.startswith("devkit-agt is imported")
    [violation] = check(RULE, tmp_path, {**project([]), "src/consumer/main.py": "from devkit import advisory"})
    assert violation.message.startswith("devkit-advisory is imported")


def test_other_devkit_modules_need_devkit_agt(tmp_path: Path) -> None:
    files = {**project(["devkit-advisory>=0.1"]), "src/consumer/main.py": "from devkit.rules import Severity"}
    [violation] = check(RULE, tmp_path, files)
    assert violation.message.startswith("devkit-agt is imported")
    assert check(RULE, tmp_path, {**files, **project(["devkit-agt>=0.1"])}) == []
    # The distribution named devkit on PyPI is an unrelated project.
    [violation] = check(RULE, tmp_path, {**files, **project(["devkit>=0.1"])})
    assert violation.message.startswith("devkit-agt is imported")


@pytest.mark.parametrize("declared", ["App_HTTP.Client[extra]>=1; python_version >= '3.12'", "app-http-client"])
def test_optional_and_normalized_declarations_count(tmp_path: Path, declared: str) -> None:
    manifest = project([])["pyproject.toml"] + f"[project.optional-dependencies]\nhttp = [{json.dumps(declared)}]\n"
    files = {"pyproject.toml": manifest, "src/consumer/main.py": "from app_http_client import get_http_client"}
    assert check(RULE, tmp_path, files) == []
