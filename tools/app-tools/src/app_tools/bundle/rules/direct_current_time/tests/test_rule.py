"""``RULE-app-direct-current-time``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from devkit.rules.testing import check, load_rule

RULE = load_rule(__file__)


def project(dependencies: list[str], name: str = "consumer") -> dict[str, str]:
    """A package manifest; the module under test goes to ``src/consumer/main.py``."""
    return {"pyproject.toml": f'[project]\nname = "{name}"\ndependencies = {json.dumps(dependencies)}\n'}


@pytest.mark.parametrize(
    "code",
    [
        "from datetime import datetime as D\nD.now()",
        "import datetime as dt\ndt.datetime.utcnow()",
        "from datetime import date\ndate.today()",
    ],
)
def test_clock_reads_warn_through_aliases(tmp_path: Path, code: str) -> None:
    [violation] = check(RULE, tmp_path, {**project(["app-layer-base"]), "src/consumer/main.py": code})
    assert violation.severity.value == "warning" and "get_current_utc_" in violation.remediation


@pytest.mark.parametrize(
    "code",
    [
        'import datetime\ndatetime.timedelta(days=1)\ndatetime.datetime.fromisoformat("2026-01-01")',
        "from sqlalchemy import func\nfunc.now()",
        "from time import monotonic\nmonotonic()",
    ],
)
def test_other_time_functions_are_allowed(tmp_path: Path, code: str) -> None:
    assert check(RULE, tmp_path, {**project(["app-layer-base"]), "src/consumer/main.py": code}) == []


def test_packages_without_app_layer_base_are_not_checked(tmp_path: Path) -> None:
    assert (
        check(RULE, tmp_path, {**project([]), "src/consumer/main.py": "import datetime\ndatetime.datetime.now()"}) == []
    )
