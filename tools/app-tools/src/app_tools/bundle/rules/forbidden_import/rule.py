"""``RULE-app-forbidden-import``: modules respect the boundaries declared in tool.app-tools.architecture.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class ForbiddenImportRule(ArchitectureRule):
    rule_id = "RULE-app-forbidden-import"
