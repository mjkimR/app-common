"""``RULE-app-db-factory-in-layer``: routers and services do not build their own DB engine or session factory.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class DbFactoryInLayerRule(ArchitectureRule):
    rule_id = "RULE-app-db-factory-in-layer"
