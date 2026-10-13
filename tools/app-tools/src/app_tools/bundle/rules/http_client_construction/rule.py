"""``RULE-app-http-client-construction``: packages on app-http-client use the shared client getters.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class HttpClientConstructionRule(ArchitectureRule):
    rule_id = "RULE-app-http-client-construction"
