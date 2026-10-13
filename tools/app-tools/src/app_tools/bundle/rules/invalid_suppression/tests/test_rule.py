"""``RULE-app-invalid-suppression``, loaded from this folder as devkit loads the deployed copy."""

from __future__ import annotations

from pathlib import Path

from devkit.rules.testing import check, load_rule

RULE = load_rule(__file__)


def test_unused_and_unknown_suppressions_warn(tmp_path: Path) -> None:
    source = "x = 1  # arch: ignore[RULE-app-service-commit] -- stale\ny = 2  # arch: ignore[ARCH_OLD] -- typo\n"
    found = check(RULE, tmp_path, {"services.py": source})
    assert [(v.line, v.message, v.severity.value) for v in found] == [
        (1, "Unused suppression of RULE-app-service-commit.", "warning"),
        (2, "Unknown suppression of ARCH_OLD.", "warning"),
    ]


def test_each_listed_rule_is_checked(tmp_path: Path) -> None:
    source = "value = 1  # arch: ignore[RULE-app-direct-current-time, ARCH_TYPO] -- stale\n"
    assert [v.message for v in check(RULE, tmp_path, {"main.py": source})] == [
        "Unknown suppression of ARCH_TYPO.",
        "Unused suppression of RULE-app-direct-current-time.",
    ]


def test_a_suppression_matching_a_finding_is_valid(tmp_path: Path) -> None:
    source = "session.commit()  # arch: ignore[RULE-app-service-commit] -- legacy boundary\n"
    assert check(RULE, tmp_path, {"services.py": source}) == []
