"""Static architectural constraint validator for app-common applications."""

from __future__ import annotations

import ast
import io
import json
import re
import sys
import tokenize
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

import click

from app_tools.architecture_boundaries import BoundaryChecks
from app_tools.architecture_hygiene import ArchViolation, HygieneVisitor


class ArchitecturalVisitor(ast.NodeVisitor):
    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.violations: list[ArchViolation] = []
        self._rel_path = str(file_path)
        self._is_api_file = "api" in file_path.parts or file_path.stem in ("router", "routes")
        self._is_service_file = "services" in file_path.parts or file_path.stem in ("service", "services")
        self._source_root = next((p for p in file_path.resolve().parents if p.name == "src"), None)
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

    def _check_import(self, node: ast.Import | ast.ImportFrom, name: str) -> None:
        # query_options is a public value object used by generated routers, not a repository.
        if self._is_api_file and "repos" in name.split(".") and name != "app_layer_base.base.repos.query_options":
            self.violations.append(
                ArchViolation(
                    "ARCH_ROUTER_REPO_IMPORT",
                    self._rel_path,
                    node.lineno,
                    f"Router/API module directly imports repository '{name}'.",
                    "Delegate repository access to a UseCase or Service.",
                )
            )
        if self._source_root is None or not name or (isinstance(node, ast.ImportFrom) and node.level):
            return
        package = self.file_path.resolve().relative_to(self._source_root).parts[0]
        imported = name.split(".")[0]
        rule = None
        if package == "app_error" and imported != package and imported not in sys.stdlib_module_names:
            rule = "ARCH_ERROR_DEPENDENCY"
        package_dir = self._source_root.parent
        if package_dir.parent.name == "adapters":
            siblings = {
                module.name
                for module in package_dir.parent.glob("*/src/*")
                if module.is_dir() and (module / "__init__.py").exists()
            }
            if imported in siblings and imported != package:
                rule = "ARCH_ADAPTER_DEPENDENCY"
        if rule:
            self.violations.append(
                ArchViolation(
                    rule,
                    self._rel_path,
                    node.lineno,
                    f"Package '{package}' imports forbidden dependency '{imported}'.",
                    "Keep app-error standard-library-only and adapters independent of sibling adapters.",
                )
            )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self._check_import(node, alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        # Include imported modules: `from feature import repos` is also a layer bypass.
        if "repos" in mod.split("."):
            self._check_import(node, mod)
        elif any(alias.name == "repos" for alias in node.names):
            self._check_import(node, f"{mod}.repos".lstrip("."))
        elif not node.level:
            self._check_import(node, mod)
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


def suppressed_lines(source: str) -> dict[int, set[str]]:
    """Only explicit rule codes in real inline comments suppress diagnostics."""
    result: dict[int, set[str]] = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        match = re.fullmatch(r"#\s*arch:\s*ignore\[([A-Z_, ]+)\]\s*--\s*(\S.*)", token.string)
        if match:
            result[token.start[0]] = {code.strip() for code in match[1].split(",")}
    return result


def scan_directory(targets: Sequence[Path]) -> list[ArchViolation]:
    violations: list[ArchViolation] = []
    seen: set[Path] = set()
    boundaries = BoundaryChecks()
    for target in targets:
        boundaries.configuration(target)
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
            if {"tests", "alembic", "migrations"}.intersection(py_file.parts) or py_file.resolve() in seen:
                continue
            seen.add(py_file.resolve())
            if boundaries.configuration(py_file)[1] is None:
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
                visitor = ArchitecturalVisitor(py_file)
                visitor.visit(tree)
                visitor.violations.extend(boundaries.inspect(py_file, tree))
                hygiene = HygieneVisitor(py_file)
                hygiene.visit(tree)
                visitor.violations.extend(hygiene.violations)
                ignored = suppressed_lines(source)
                violations.extend(v for v in visitor.violations if v.rule not in ignored.get(v.line, set()))
                known = {
                    "ARCH_FORBIDDEN_IMPORT",
                    "ARCH_ROUTER_REPO_IMPORT",
                    "ARCH_SERVICE_COMMIT",
                    "ARCH_HOOK_SUPER_CALL",
                    "ARCH_ERROR_DEPENDENCY",
                    "ARCH_ADAPTER_DEPENDENCY",
                    "ARCH_PARSE_ERROR",
                    "ARCH_HTTP_CLIENT_CONSTRUCTION",
                    "ARCH_DIRECT_CURRENT_TIME",
                    "ARCH_SHARED_CLIENT_CLOSE",
                    "ARCH_UNDECLARED_DEPENDENCY",
                    "ARCH_DB_FACTORY_IN_LAYER",
                }
                for line, codes in ignored.items():
                    actual = {v.rule for v in visitor.violations if v.line == line}
                    for code in sorted(codes - actual):
                        problem = "unknown" if code not in known else "unused"
                        violations.append(
                            ArchViolation(
                                "ARCH_INVALID_SUPPRESSION",
                                str(py_file),
                                line,
                                f"{problem.capitalize()} suppression code {code}.",
                                "Remove the stale exception or use the exact rule code on the diagnostic line.",
                                "warning",
                            )
                        )
            except (SyntaxError, UnicodeDecodeError, tokenize.TokenError) as exc:
                violations.append(
                    ArchViolation(
                        "ARCH_PARSE_ERROR",
                        str(py_file),
                        getattr(exc, "lineno", None) or 1,
                        f"Cannot inspect Python source: {exc}",
                        "Fix the syntax or UTF-8 encoding and rerun check-arch.",
                    )
                )
    return [*boundaries.violations, *violations]


@click.command("check-arch")
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON output.")
def check_arch(paths: tuple[str, ...], as_json: bool) -> None:
    """Validate architectural layer boundaries and hook invariants."""
    target_paths = [Path(p) for p in paths] if paths else [Path.cwd()]
    violations = scan_directory(target_paths)

    errors = sum(v.severity == "error" for v in violations)
    warnings = len(violations) - errors

    if as_json:
        report = {
            "status": "failed" if errors else "passed",
            "errors_count": errors,
            "warnings_count": warnings,
            "violations_count": len(violations),
            "violations": [asdict(v) for v in violations],
        }
        click.echo(json.dumps(report, indent=2))
        if errors:
            raise SystemExit(1)
        return

    if not violations:
        click.echo("Architectural check passed! No layer or hook invariant violations found.")
        return

    click.echo(f"Architecture: {errors} error(s), {warnings} warning(s).", err=True)
    for v in violations:
        prefix = "WARN" if v.severity == "warning" else "ERROR"
        click.echo(
            f"{prefix} [{v.rule}] {v.file}:{v.line}: {v.message} Fix: {v.fix} Guide: app-tools guide show {v.guide}",
            err=True,
        )

    if errors:
        raise SystemExit(1)
