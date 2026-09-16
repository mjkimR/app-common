"""Typed non-CRUD commands and caller-owned execution scopes.

No database, transport, or application settings are configured by this module.
"""

from app_layer_base.application.commands import Command, CommandHandler, execute_command
from app_layer_base.application.transactions import TransactionScope, TransactionScopeError

__all__ = ["Command", "CommandHandler", "TransactionScope", "TransactionScopeError", "execute_command"]
