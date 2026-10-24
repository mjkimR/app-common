"""``RULE-app-db-factory-in-layer``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

import json
from pathlib import Path

from devkit_agt.features.rules.services.testing import check, load_rule

RULE = load_rule(__file__)


def project(dependencies: list[str], name: str = "consumer") -> dict[str, str]:
    """A package manifest; the module under test goes to ``src/consumer/main.py``."""
    return {"pyproject.toml": f'[project]\nname = "{name}"\ndependencies = {json.dumps(dependencies)}\n'}


def test_only_routers_and_services_are_checked(tmp_path: Path) -> None:
    code = 'from sqlalchemy.ext.asyncio import create_async_engine as create\ncreate("url")'
    assert check(RULE, tmp_path, {**project(["app-layer-base"]), "src/consumer/main.py": code}) == []
    found = check(RULE, tmp_path, {"src/consumer/services.py": code})
    assert [(v.file, v.line, v.severity.value) for v in found] == [("src/consumer/services.py", 2, "warning")]
