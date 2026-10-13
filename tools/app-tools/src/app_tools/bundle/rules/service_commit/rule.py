"""``RULE-app-service-commit``: services leave commit and rollback to their caller.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class ServiceCommitRule(ArchitectureRule):
    rule_id = "RULE-app-service-commit"
