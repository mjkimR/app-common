"""``RULE-app-architecture-config``: tool.app-tools.architecture in pyproject.toml is well formed.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class ArchitectureConfigRule(ArchitectureRule):
    rule_id = "RULE-app-architecture-config"
