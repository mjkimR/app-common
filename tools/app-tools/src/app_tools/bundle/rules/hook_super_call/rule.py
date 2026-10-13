"""``RULE-app-hook-super-call``: hook methods do not chain through super().

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class HookSuperCallRule(ArchitectureRule):
    rule_id = "RULE-app-hook-super-call"
