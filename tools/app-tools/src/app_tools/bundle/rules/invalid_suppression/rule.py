"""``RULE-app-invalid-suppression``: every `# arch: ignore[...]` comment names a rule reported on its line.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class InvalidSuppressionRule(ArchitectureRule):
    rule_id = "RULE-app-invalid-suppression"
