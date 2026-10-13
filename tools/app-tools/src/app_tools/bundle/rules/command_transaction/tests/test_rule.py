"""``RULE-app-command-transaction``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

from pathlib import Path

import pytest
from devkit.rules.testing import check, load_rule

RULE = load_rule(__file__)

CONFIG = """[project]
name = "consumer"
[[tool.app-tools.architecture.commands]]
source = "consumer.features"
"""


@pytest.mark.parametrize(
    "call",
    [
        "ctx.tx.session.commit()",
        "ctx.tx.session.rollback()",
        "ctx.transaction()",
        "ctx.store.tx()",
        "session.begin()",
        "session.begin_nested()",
    ],
)
def test_transaction_control_is_reported_even_in_private_helpers(tmp_path: Path, call: str) -> None:
    files = {
        "pyproject.toml": CONFIG,
        "src/consumer/features/books/commands.py": f"async def _helper(ctx):\n    await {call}\n",
    }
    assert [(v.line, v.severity.value) for v in check(RULE, tmp_path, files)] == [(2, "error")]


def test_other_modules_may_control_transactions(tmp_path: Path) -> None:
    files = {"pyproject.toml": CONFIG, "src/consumer/features/books/usecases.py": "session.commit()\n"}
    assert check(RULE, tmp_path, files) == []
