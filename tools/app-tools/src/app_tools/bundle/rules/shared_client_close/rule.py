"""``RULE-app-shared-client-close``: application code does not close the shared HTTP client.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class SharedClientCloseRule(ArchitectureRule):
    rule_id = "RULE-app-shared-client-close"
