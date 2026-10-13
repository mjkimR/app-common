"""``RULE-app-adapter-dependency``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

from pathlib import Path

from devkit.rules.testing import check, load_rule

RULE = load_rule(__file__)


def test_an_adapter_importing_a_sibling_adapter_is_reported(tmp_path: Path) -> None:
    files = {
        "packages/adapters/app_first/src/app_first/__init__.py": "",
        "packages/adapters/app_second/src/app_second/__init__.py": "",
        "packages/adapters/app_first/src/app_first/client.py": "from app_second.client import Client\nimport app_first\n",
    }
    found = check(RULE, tmp_path, files, targets=["packages/adapters/app_first/src/app_first/client.py"])
    assert [(v.line, v.message) for v in found] == [
        (1, "Adapter package 'app_first' imports sibling adapter 'app_second'.")
    ]
