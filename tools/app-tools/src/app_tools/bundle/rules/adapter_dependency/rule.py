"""``RULE-app-adapter-dependency``: an adapter package does not import a sibling adapter.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class AdapterDependencyRule(ArchitectureRule):
    rule_id = "RULE-app-adapter-dependency"
