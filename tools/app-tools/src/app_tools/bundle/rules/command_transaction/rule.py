"""``RULE-app-command-transaction``: command modules leave the execution scope to their caller.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class CommandTransactionRule(ArchitectureRule):
    rule_id = "RULE-app-command-transaction"
