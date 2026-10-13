"""``RULE-app-router-repo-import``: routers and API modules reach repositories through a usecase or service.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class RouterRepoImportRule(ArchitectureRule):
    rule_id = "RULE-app-router-repo-import"
