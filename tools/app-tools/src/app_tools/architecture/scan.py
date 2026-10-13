"""Static architecture checks over Python sources; never imports consumer code."""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections.abc import Callable, Iterable
from pathlib import Path

from app_tools.architecture.boundaries import BoundaryChecks
from app_tools.architecture.hygiene import HygieneVisitor
from app_tools.architecture.model import RULES, ArchViolation, relative_parts

EXCLUDED_PARTS = frozenset({"tests", "alembic", "migrations"})
SUPPRESSION = re.compile(r"#\s*arch:\s*ignore\[([A-Za-z0-9_, -]+)\]\s*--\s*(\S.*)")


class ArchitecturalVisitor(ast.NodeVisitor):
    def __init__(self, file_path: Path, root: Path | None = None) -> None:
        self.file_path = file_path
        self.violations: list[ArchViolation] = []
        self._rel_path = str(file_path)
        parts = relative_parts(file_path, root)
        self._is_api_file = "api" in parts or file_path.stem in ("router", "routes")
        self._is_service_file = "services" in parts or file_path.stem in ("service", "services")
        self._source_root = next(
            (p for p in file_path.resolve().parents if p.name == "src" and (root is None or p.is_relative_to(root))),
            None,
        )
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
                    "RULE-app-router-repo-import",
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
        package_dir = self._source_root.parent
        if package_dir.parent.name != "adapters" or imported == package:
            return
        siblings = {
            module.name
            for module in package_dir.parent.glob("*/src/*")
            if module.is_dir() and (module / "__init__.py").exists()
        }
        if imported in siblings:
            self.violations.append(
                ArchViolation(
                    "RULE-app-adapter-dependency",
                    self._rel_path,
                    node.lineno,
                    f"Adapter package '{package}' imports sibling adapter '{imported}'.",
                    "Keep adapters independent of sibling adapters; compose them in the application.",
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
                        "RULE-app-hook-super-call",
                        self._rel_path,
                        node.lineno,
                        f"Hook '{self._current_class}.{self._current_function}' calls super().{node.func.attr}().",
                        "Hooks are independent protocol units; chaining is managed by the service executor. Remove super().",
                    )
                )

        # Check commit/rollback in Service
        if self._is_service_file and isinstance(node.func, ast.Attribute) and node.func.attr in ("commit", "rollback"):
            self.violations.append(
                ArchViolation(
                    "RULE-app-service-commit",
                    self._rel_path,
                    node.lineno,
                    f"Service directly invokes '{node.func.attr}()' on session.",
                    "Services must not manage transaction boundaries. Delegate commit/rollback to UseCase or session context.",
                )
            )

        self.generic_visit(node)


def suppressed_lines(source: str) -> dict[int, set[str]]:
    """Only explicit rule IDs with a reason, in real inline comments, suppress findings."""
    result: dict[int, set[str]] = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type != tokenize.COMMENT:
            continue
        match = SUPPRESSION.fullmatch(token.string)
        if match:
            result[token.start[0]] = {code.strip() for code in match[1].split(",")}
    return result


def is_excluded(path: Path, root: Path | None = None) -> bool:
    """Tests and migrations are outside the architecture checks."""
    return bool(EXCLUDED_PARTS.intersection(relative_parts(path, root)))


def scan_files(
    files: Iterable[Path],
    *,
    root: Path | None = None,
    read: Callable[[Path], str] = lambda path: path.read_text(encoding="utf-8"),
) -> list[ArchViolation]:
    """Every finding for ``files``; manifest lookups stop at ``root`` or the Git repository boundary."""
    violations: list[ArchViolation] = []
    seen: set[Path] = set()
    boundaries = BoundaryChecks(root)
    for py_file in files:
        if py_file.suffix != ".py" or is_excluded(py_file, root) or py_file.resolve() in seen:
            continue
        seen.add(py_file.resolve())
        if boundaries.configuration(py_file)[1] is None:
            continue
        try:
            source = read(py_file)
            tree = ast.parse(source, filename=str(py_file))
            visitor = ArchitecturalVisitor(py_file, root)
            visitor.visit(tree)
            found = [*visitor.violations, *boundaries.inspect(py_file, tree)]
            hygiene = HygieneVisitor(py_file, root)
            hygiene.visit(tree)
            found.extend(hygiene.violations)
            ignored = suppressed_lines(source)
        except (SyntaxError, UnicodeDecodeError, tokenize.TokenError) as exc:
            violations.append(
                ArchViolation(
                    "RULE-app-parse-error",
                    str(py_file),
                    getattr(exc, "lineno", None) or 1,
                    f"Cannot inspect Python source: {exc}",
                    "Fix the syntax or UTF-8 encoding and rerun `devkit rules check`.",
                )
            )
            continue
        violations.extend(v for v in found if v.rule not in ignored.get(v.line, set()))
        for line, codes in ignored.items():
            actual = {v.rule for v in found if v.line == line}
            for code in sorted(codes - actual):
                problem = "Unknown" if code not in RULES else "Unused"
                violations.append(
                    ArchViolation(
                        "RULE-app-invalid-suppression",
                        str(py_file),
                        line,
                        f"{problem} suppression of {code}.",
                        "Remove the stale exception or use the exact rule ID on the diagnostic line.",
                    )
                )
    return [*boundaries.violations, *violations]
