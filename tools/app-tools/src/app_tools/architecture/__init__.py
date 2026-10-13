"""Static architecture checks for app-common applications.

The checks run as devkit rules: the `app-common` bundle ships one rule package per entry of
``RULES`` (``bundle/rules/<slug>/``), and ``devkit rules check`` evaluates them.
"""

from app_tools.architecture.model import RULES, ArchViolation, RuleSpec
from app_tools.architecture.scan import is_excluded, scan_files

__all__ = ["RULES", "ArchViolation", "RuleSpec", "is_excluded", "scan_files"]
