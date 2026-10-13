"""``RULE-app-router-repo-import``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

from pathlib import Path

import pytest
from devkit.rules.testing import check, load_rule

RULE = load_rule(__file__)


def test_a_router_importing_a_repository_is_reported(tmp_path: Path) -> None:
    found = check(RULE, tmp_path, {"app/api/v1/items.py": "from app.features.items.repos import ItemRepository\n"})
    assert [(v.file, v.line, v.severity.value) for v in found] == [("app/api/v1/items.py", 1, "error")]
    assert found[0].message == "Router/API module directly imports repository 'app.features.items.repos'."


@pytest.mark.parametrize(
    "source",
    [
        "from feature.repos.item import Repository",
        "from feature import repos",
        "from . import repos",
        "import feature.repos.item",
    ],
)
def test_repository_import_forms(tmp_path: Path, source: str) -> None:
    assert [v.file for v in check(RULE, tmp_path, {"router.py": source})] == ["router.py"]


@pytest.mark.parametrize(
    "source",
    [
        "from feature.repository_utils import helper",
        "from app_layer_base.base.repos.query_options import ListQueryOptions",
        "from app.features.items.usecases.crud import GetItemUseCase",
    ],
)
def test_usecases_and_repository_value_objects_are_allowed(tmp_path: Path, source: str) -> None:
    assert check(RULE, tmp_path, {"app/api/items.py": source}) == []


def test_directories_above_the_workspace_never_classify_files(tmp_path: Path) -> None:
    workspace = tmp_path / "tests" / "api" / "repo"  # e.g. a clone under ~/work/api/
    source = "from app.features.items.repos import ItemRepository\n"
    assert check(RULE, workspace, {"app/features/items/models.py": source}) == []
    assert [v.file for v in check(RULE, workspace, {"app/api/items.py": source})] == ["app/api/items.py"]
