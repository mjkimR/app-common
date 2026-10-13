"""``RULE-app-direct-current-time``: packages on app-layer-base read the clock through its UTC utilities.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class DirectCurrentTimeRule(ArchitectureRule):
    rule_id = "RULE-app-direct-current-time"
