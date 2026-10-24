"""``RULE-app-parse-error``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

from pathlib import Path

from devkit_agt.features.rules.services.testing import check, load_rule

RULE = load_rule(__file__)


def test_a_file_that_does_not_parse_is_reported(tmp_path: Path) -> None:
    found = check(RULE, tmp_path, {"broken.py": "def broken(", "fine.py": "x = 1\n"})
    assert [(v.file, v.severity.value) for v in found] == [("broken.py", "error")]
    assert found[0].message.startswith("Cannot inspect Python source: ")


def test_tests_are_not_parsed(tmp_path: Path) -> None:
    assert check(RULE, tmp_path, {"tests/fixtures/broken.py": "def broken("}) == []
