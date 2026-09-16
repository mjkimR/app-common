"""Opt-in command-module conventions; never import consumer source."""

from __future__ import annotations

import ast
from pathlib import Path

from app_tools.architecture_hygiene import ArchViolation


def _concrete_annotation(node: ast.expr | None) -> bool:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        try:
            node = ast.parse(node.value, mode="eval").body
        except SyntaxError:
            return False
    if isinstance(node, ast.Name):
        return node.id not in {"Any", "object", "dict", "list", "BaseModel"}
    return isinstance(node, ast.Attribute) and node.attr not in {"Any", "BaseModel"}


def inspect_commands(path: Path, tree: ast.AST) -> list[ArchViolation]:
    """Public functions are commands; helpers are private, orchestration lives elsewhere.

    Annotation identity/aliases and registered DTO ownership are checked at test
    time by assert_command_contracts. Transaction calls are a naming convention,
    not interprocedural analysis; import boundaries complement this check.
    """
    violations: list[ArchViolation] = []
    for node in getattr(tree, "body", []):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) or node.name.startswith("_"):
            continue
        valid = False
        if isinstance(node, ast.AsyncFunctionDef):
            args = node.args
            positional = [*args.posonlyargs, *args.args]
            valid = (
                len(positional) == 2
                and not (args.vararg or args.kwarg or args.kwonlyargs or args.defaults or node.decorator_list)
                and all(_concrete_annotation(arg.annotation) for arg in positional)
                and _concrete_annotation(node.returns)
            )
        if not valid:
            violations.append(
                ArchViolation(
                    "ARCH_COMMAND_SIGNATURE",
                    str(path),
                    node.lineno,
                    f"Public command {node.name!r} must be an undecorated async function with typed context, input and output.",
                    "Use async def operation(ctx: Context, inp: Input) -> Output; put private helpers or usecases elsewhere.",
                    guide="backend/commands",
                )
            )
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr
            in {
                "commit",
                "rollback",
                "begin",
                "begin_nested",
                "transaction",
                "tx",
            }
        ):
            violations.append(
                ArchViolation(
                    "ARCH_COMMAND_TRANSACTION",
                    str(path),
                    node.lineno,
                    f"Command module calls {node.func.attr}(); its caller owns the execution scope.",
                    "Use the supplied context.tx; put explicit short-transaction orchestration in a usecase with an application policy.",
                    guide="backend/commands",
                )
            )
    return violations
