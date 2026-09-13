"""Static architectural constraint validator for app-common applications."""

from __future__ import annotations

import ast
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import click


@dataclass
class ArchViolation:
    rule: str
    file: str
    line: int
    message: str
    fix: str


class ArchitecturalVisitor(ast.NodeVisitor):
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.violations: list[ArchViolation] = []
        self._rel_path = str(file_path)
        self._is_api_file = "api" in file_path.parts or file_path.stem in ("router", "routes")
        self._is_service_file = "services" in file_path.parts or file_path.stem in ("service", "services")
        self._current_class: str | None = None
        self._is_hook_class = False
        self._current_function: str | None = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        prev_class = self._current_class
        prev_is_hook = self._is_hook_class

        self._current_class = node.name
        self._is_hook_class = node.name.endswith("Hook") or any(
            isinstance(b, ast.Name) and b.id.endswith("Hook") for b in node.bases
        )

        self.generic_visit(node)

        self._current_class = prev_class
        self._is_hook_class = prev_is_hook

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        prev_func = self._current_function
        self._current_function = node.name
        self.generic_visit(node)
        self._current_function = prev_func

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        prev_func = self._current_function
        self._current_function = node.name
        self.generic_visit(node)
        self._current_function = prev_func

    def visit_Import(self, node: ast.Import) -> None:
        if self._is_api_file:
            for alias in node.names:
                name = alias.name
                if ".repos" in name or name.endswith(".repos") or name == "repos":
                    self.violations.append(
                        ArchViolation(
                            rule="ARCH_ROUTER_REPO_IMPORT",
                            file=self._rel_path,
                            line=node.lineno,
                            message=f"Router/API module directly imports repository '{name}'.",
                            fix="Routers must only interact with UseCases or Services. Remove repository import.",
                        )
                    )
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if self._is_api_file:
            mod = node.module or ""
            if mod.endswith(".repos") or mod == "repos":
                self.violations.append(
                    ArchViolation(
                        rule="ARCH_ROUTER_REPO_IMPORT",
                        file=self._rel_path,
                        line=node.lineno,
                        message=f"Router/API module directly imports from repository module '{mod}'.",
                        fix="Routers must only interact with UseCases or Services. Remove repository import.",
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check super() call in Hook class methods (excluding __init__)
        if (
            self._is_hook_class
            and self._current_function
            and self._current_function != "__init__"
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Call)
        ):
            inner = node.func.value
            if isinstance(inner.func, ast.Name) and inner.func.id == "super":
                self.violations.append(
                    ArchViolation(
                        rule="ARCH_HOOK_SUPER_CALL",
                        file=self._rel_path,
                        line=node.lineno,
                        message=f"Hook '{self._current_class}.{self._current_function}' calls super().{node.func.attr}().",
                        fix="Hooks are independent protocol units; chaining is managed by the service executor. Remove super().",
                    )
                )

        # Check commit/rollback in Service
        if self._is_service_file and isinstance(node.func, ast.Attribute) and node.func.attr in ("commit", "rollback"):
            self.violations.append(
                ArchViolation(
                    rule="ARCH_SERVICE_COMMIT",
                    file=self._rel_path,
                    line=node.lineno,
                    message=f"Service directly invokes '{node.func.attr}()' on session.",
                    fix="Services must not manage transaction boundaries. Delegate commit/rollback to UseCase or session context.",
                )
            )

        self.generic_visit(node)


def scan_directory(targets: Sequence[Path]) -> list[ArchViolation]:
    violations: list[ArchViolation] = []
    for target in targets:
        if target.is_file() and target.suffix == ".py":
            files = [target]
        elif target.is_dir():
            files = [
                p
                for p in target.rglob("*.py")
                if not any(
                    part.startswith(".") or part in ("node_modules", ".venv", "venv", "dist", "build", "__pycache__")
                    for part in p.parts
                )
            ]
        else:
            continue

        for py_file in files:
            # Skip test files and migration files from architectural layer checks
            if "tests" in py_file.parts or "alembic" in py_file.parts:
                continue
            try:
                tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
                visitor = ArchitecturalVisitor(py_file)
                visitor.visit(tree)
                violations.extend(visitor.violations)
            except (SyntaxError, UnicodeDecodeError):
                continue
    return violations


@click.command("check-arch")
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON output.")
def check_arch(paths: tuple[str, ...], as_json: bool) -> None:
    """Validate architectural layer boundaries and hook invariants."""
    target_paths = [Path(p) for p in paths] if paths else [Path.cwd()]
    violations = scan_directory(target_paths)

    if as_json:
        report = {
            "status": "failed" if violations else "passed",
            "violations_count": len(violations),
            "violations": [asdict(v) for v in violations],
        }
        click.echo(json.dumps(report, indent=2))
        if violations:
            raise SystemExit(1)
        return

    if not violations:
        click.echo("Architectural check passed! No layer or hook invariant violations found.")
        return

    click.echo(f"Found {len(violations)} architectural violation(s):\n", err=True)
    for v in violations:
        click.echo(f"[{v.rule}] {v.file}:{v.line}", err=True)
        click.echo(f"  Issue: {v.message}", err=True)
        click.echo(f"  Fix:   {v.fix}\n", err=True)

    raise SystemExit(1)
