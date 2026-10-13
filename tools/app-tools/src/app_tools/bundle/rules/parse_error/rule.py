"""``RULE-app-parse-error``: Python sources can be parsed for the architecture checks.

The check runs in ``app_tools.architecture``, one AST pass shared by every app-common rule; this package
declares the rule, its guide (``guide.md``) and its tests.
"""

from app_tools.architecture.rule import ArchitectureRule


class ParseErrorRule(ArchitectureRule):
    rule_id = "RULE-app-parse-error"
