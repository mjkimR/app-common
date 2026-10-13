"""``RULE-app-undeclared-dependency``: imported app-common and devkit packages are declared by the importer.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class UndeclaredDependencyRule(ArchitectureRule):
    rule_id = "RULE-app-undeclared-dependency"
