"""Run the bundle's rules through `devkit rules check`, as a project runs them."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from click.testing import CliRunner
from devkit.cli import cli as devkit_cli

BUNDLE = Path(__file__).resolve().parents[3] / "src/app_tools/bundle"
BUNDLE_RULES = BUNDLE / "rules"


def rules_check(workspace: Path, *targets: Path) -> tuple[int, dict[str, Any]]:
    """`devkit rules check --format json` with the bundle's rules, in ``workspace``: (exit code, document)."""
    args = ["rules", "check", "-w", str(workspace), "--rules-dir", str(BUNDLE_RULES), "--format", "json"]
    result = CliRunner().invoke(devkit_cli, [*args, *(str(target) for target in targets)])
    return result.exit_code, json.loads(result.stdout)


def app_violations(document: dict[str, Any]) -> list[dict[str, Any]]:
    return [v for v in document["violations"] if v["rule_id"].startswith("RULE-app-")]
