"""The devkit rule adapter: one ``devkit rules`` rule per entry of ``RULES``, one scan per evaluation.

Each rule is a plugin package of the ``app-common`` bundle, ``bundle/rules/<slug>/``: ``rule.py`` subclasses
``ArchitectureRule`` with its ``rule_id``, ``guide.md`` beside it is the guide, and ``tests/`` holds its tests. The
checks themselves stay here, in one AST pass shared by every rule: suppression comments and
``RULE-app-invalid-suppression`` need every rule's findings on a line.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from devkit_agt.features.rules import Phase, RuleContext, Severity, Violation
from devkit_agt.features.rules.services.builtins import BaseRule

from app_tools.architecture.model import RULES, ArchViolation
from app_tools.architecture.scan import scan_files

_last_scan: tuple[object, list[ArchViolation]] | None = None


def findings(ctx: RuleContext) -> list[ArchViolation]:
    """Scan the targeted Python files once per evaluation; every architecture rule filters the result.

    Keyed on the context, not its cache: a caller may share one cache across evaluations of other targets.
    """
    global _last_scan
    if _last_scan is not None and _last_scan[0] is ctx:
        return _last_scan[1]
    root = ctx.workspace_root.resolve()
    files = [
        path
        for path in ctx.cache.find_files(root, extensions=(".py",))
        if ctx.is_file_targeted(path.relative_to(root).as_posix())
    ]
    result = scan_files(files, root=root, read=ctx.cache.read_text)
    _last_scan = (ctx, result)
    return result


class ArchitectureRule(BaseRule):
    """Base of the bundle's rule classes (``rules/<slug>/rule.py``); ``rule_id`` names the ``RULES`` entry.

    ``guide.md`` resolves next to the subclass's module, so each rule package carries its own guide.
    """

    rule_id: ClassVar[str]

    def __init__(self) -> None:
        spec = RULES[self.rule_id]
        super().__init__(
            id=spec.id,
            name=spec.name,
            description=spec.description,
            phase=Phase.LINTER,
            severity=Severity(spec.severity),
            guide="guide.md",
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
