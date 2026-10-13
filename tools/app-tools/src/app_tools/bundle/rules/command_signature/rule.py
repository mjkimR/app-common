"""``RULE-app-command-signature``: public command functions have the command shape.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class CommandSignatureRule(ArchitectureRule):
    rule_id = "RULE-app-command-signature"
