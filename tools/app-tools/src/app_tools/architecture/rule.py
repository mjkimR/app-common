"""The devkit rule adapter: one ``devkit rules`` rule per entry of ``RULES``, one scan per evaluation."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from devkit.rules import Phase, RuleContext, Severity, Violation
from devkit.rules.rules import BaseRule

from app_tools.architecture.model import RULES, ArchViolation
from app_tools.architecture.scan import scan_files

# The bundle deploys rule files to rules/ and the skill to skills/app-common/, side by side.
SKILL_FROM_RULES = "../skills/app-common"

_last_scan: tuple[object, list[ArchViolation]] | None = None


def guide_document(topic: str) -> str:
    """The skill reference of a catalog topic, relative to the deployed rule file."""
    relative = f"references/{topic}.md" if "/" in topic else f"references/{topic}/index.md"
    return f"{SKILL_FROM_RULES}/{relative}"


def findings(ctx: RuleContext) -> list[ArchViolation]:
    """Scan the targeted Python files once per evaluation; every architecture rule filters the result."""
    global _last_scan
    if _last_scan is not None and _last_scan[0] is ctx.cache:
        return _last_scan[1]
    root = ctx.workspace_root.resolve()
    files = [
        path
        for path in ctx.cache.find_files(root, extensions=(".py",))
        if ctx.is_file_targeted(path.relative_to(root).as_posix())
    ]
    result = scan_files(files, root=root, read=ctx.cache.read_text)
    _last_scan = (ctx.cache, result)
    return result


class ArchitectureRule(BaseRule):
    """Base of the rule classes in the bundle's ``rules/architecture.py``; ``rule_id`` names the ``RULES`` entry."""

    rule_id: ClassVar[str]

    def __init__(self) -> None:
        spec = RULES[self.rule_id]
        super().__init__(
            id=spec.id,
            name=spec.name,
            description=spec.description,
            phase=Phase.LINTER,
            severity=Severity(spec.severity),
            guide=guide_document(spec.guide),
        )

    def check(self, ctx: RuleContext) -> list[Violation]:
        root = ctx.workspace_root.resolve()
        violations: list[Violation] = []
        for finding in findings(ctx):
            if finding.rule != self.id:
                continue
            path = Path(finding.file).resolve()
            relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else finding.file
            violations.append(
                Violation(
                    rule_id=self.id,
                    file=relative,
                    line=finding.line,
                    message=finding.message,
                    remediation=finding.fix,
                )
            )
        return violations
