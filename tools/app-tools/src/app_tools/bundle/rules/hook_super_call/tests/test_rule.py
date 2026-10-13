"""``RULE-app-hook-super-call``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

from pathlib import Path

from devkit.rules.testing import check, load_rule

RULE = load_rule(__file__)


def test_a_hook_chaining_through_super_is_reported(tmp_path: Path) -> None:
    source = "class AuditHook:\n    async def create_pre(self, op):\n        await super().create_pre(op)\n"
    found = check(RULE, tmp_path, {"app/features/items/services.py": source})
    assert [(v.line, v.message) for v in found] == [(3, "Hook 'AuditHook.create_pre' calls super().create_pre().")]


def test_init_and_independent_hooks_are_allowed(tmp_path: Path) -> None:
    source = (
        "class AuditHook(BaseHook):\n"
        "    def __init__(self):\n        super().__init__()\n"
        "    async def create_pre(self, op):\n        return op\n"
    )
    assert check(RULE, tmp_path, {"app/features/items/services.py": source}) == []
