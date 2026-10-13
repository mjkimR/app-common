"""``RULE-app-architecture-config``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

from pathlib import Path

import pytest
from devkit.rules.testing import check, load_rule

RULE = load_rule(__file__)

BOUNDARY = """
[project]
name = "consumer"

[[tool.app-tools.architecture.boundaries]]
name = "application"
source = "consumer.features"
forbidden_imports = ["consumer.server", "sqlalchemy"]
"""
COMMANDS = """[project]
name = "consumer"
[[tool.app-tools.architecture.commands]]
source = "consumer.features"
"""


@pytest.mark.parametrize(
    "config",
    [
        "[broken",
        '[tool.app-tools]\narchitecture = "bad"',
        '[tool.app-tools.architecture]\nboundaries = "bad"',
        BOUNDARY.replace('source = "consumer.features"', 'source = "consumer.*"'),
        BOUNDARY.replace('forbidden_imports = ["consumer.server", "sqlalchemy"]', "forbidden_imports = []"),
        BOUNDARY.replace('name = "application"', 'name = ""'),
        BOUNDARY.replace('source = "consumer.features"', 'source = "consumer.features"\nunknown = true'),
        BOUNDARY + BOUNDARY[BOUNDARY.index("[[tool.app-tools") :],
        '[tool.app-tools.architecture]\ncommands = "bad"',
        '[[tool.app-tools.architecture.commands]]\nsource = "consumer.*"',
        COMMANDS + "unknown = true",
        COMMANDS + '[[tool.app-tools.architecture.commands]]\nsource = "consumer.features"',
    ],
)
def test_an_invalid_table_is_reported_once_per_manifest(tmp_path: Path, config: str) -> None:
    files = {"pyproject.toml": config, "module.py": "x = 1\n", "other.py": "y = 2\n"}
    found = check(RULE, tmp_path, files)
    assert [(v.file, v.line, v.severity.value) for v in found] == [("pyproject.toml", 1, "error")]
    assert found[0].message.startswith("Invalid architecture configuration: ")


def test_a_valid_table_passes(tmp_path: Path) -> None:
    assert check(RULE, tmp_path, {"pyproject.toml": BOUNDARY, "src/consumer/features/a.py": "x = 1\n"}) == []
