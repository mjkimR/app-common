"""Package-aware advisories; inspect declarations without importing consumer code."""

from __future__ import annotations

import ast
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ArchViolation:
    rule: str
    file: str
    line: int
    message: str
    fix: str
    severity: str = "error"
    guide: str = "backend"


def package_context(path: Path) -> tuple[str, set[str]]:
    """The nearest project owns the file; shared environments do not enable rules."""
    for parent in path.resolve().parents:
        manifest = parent / "pyproject.toml"
        if manifest.exists():
            data = tomllib.loads(manifest.read_text(encoding="utf-8"))
            if "project" in data:
                project = data["project"]
                dependencies = list(project.get("dependencies", []))
                for extra in project.get("optional-dependencies", {}).values():
                    dependencies.extend(extra)
                names = set()
                for requirement in dependencies:
                    match = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement)
                    if match:
                        names.add(re.sub(r"[-_.]+", "-", match[0]).lower())
                return re.sub(r"[-_.]+", "-", project.get("name", "")).lower(), names
        if (parent / ".git").exists():
            break
    return "", set()


class Bindings(ast.NodeVisitor):
    """Find local names without descending into nested lexical scopes."""

    def __init__(self) -> None:
        self.names: set[str] = set()

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.names.add(node.id)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.names.add(node.name)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names.add(node.name)

    def visit_Import(self, node: ast.Import) -> None:
        self.names.update(alias.asname or alias.name.split(".")[0] for alias in node.names)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self.names.update(alias.asname or alias.name for alias in node.names)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.names.add(node.name)
        self.generic_visit(node)


class HygieneVisitor(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.package, self.dependencies = package_context(path)
        self.enabled = self.dependencies | {self.package}
        self.bindings: dict[str, str] = {}
        self.violations: list[ArchViolation] = []

    def report(self, node: ast.AST, rule: str, message: str, fix: str, guide: str) -> None:
        self.violations.append(
            ArchViolation(rule, str(self.path), getattr(node, "lineno", 1), message, fix, "warning", guide)
        )

    def resolve(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return self.bindings.get(node.id, "")
        if isinstance(node, ast.Attribute):
            prefix = self.resolve(node.value)
            return f"{prefix}.{node.attr}" if prefix else ""
        if isinstance(node, ast.Call):
            factory = self.resolve(node.func)
            if factory in {"app_http_client.get_http_client", "app_http_client.instance.get_http_client"}:
                return "shared_async_client"
            if factory in {"app_http_client.get_http_sync_client", "app_http_client.instance.get_http_sync_client"}:
                return "shared_sync_client"
        return ""

    def check_dependency(self, node: ast.AST, module: str) -> None:
        root = module.split(".")[0]
        # Restrict this rule to app-common's known public import roots.
        packages = {
            "app_error",
            "app_layer_base",
            "app_testing_base",
            "app_http_client",
            "app_file_storage",
            "app_vector_store",
            "app_ai_catalog",
            "app_mcp",
            "app_prebuilt_auth",
            "app_prebuilt_outbox",
            "app_tools",
        }
        name = root.replace("_", "-")
        if self.package and root in packages and name not in self.enabled:
            self.report(
                node,
                "ARCH_UNDECLARED_DEPENDENCY",
                f"{name} is imported but not declared by {self.package}.",
                f"Declare {name} in this package's project.dependencies or an appropriate optional dependency.",
                "local-dev",
            )

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.bindings[alias.asname or alias.name.split(".")[0]] = (
                alias.name if alias.asname else alias.name.split(".")[0]
            )
            self.check_dependency(node, alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.level:
            for alias in node.names:
                self.bindings.pop(alias.asname or alias.name, None)
            return
        module = node.module or ""
        self.check_dependency(node, module)
        for alias in node.names:
            self.bindings[alias.asname or alias.name] = f"{module}.{alias.name}"

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for expr in [*node.decorator_list, *node.args.defaults, *[d for d in node.args.kw_defaults if d]]:
            self.visit(expr)
        outer = self.bindings.copy()
        locals_ = Bindings()
        for statement in node.body:
            locals_.visit(statement)
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if node.args.vararg:
            arguments.append(node.args.vararg)
        if node.args.kwarg:
            arguments.append(node.args.kwarg)
        for name in locals_.names | {arg.arg for arg in arguments}:
            self.bindings.pop(name, None)
        for statement in node.body:
            self.visit(statement)
        self.bindings = outer
        self.bindings.pop(node.name, None)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        outer = self.bindings.copy()
        self.generic_visit(node)
        self.bindings = outer
        self.bindings.pop(node.name, None)

    def visit_Assign(self, node: ast.Assign) -> None:
        self.visit(node.value)
        value = self.resolve(node.value)
        for target in node.targets:
            for child in ast.walk(target):
                if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store):
                    self.bindings.pop(child.id, None)
            if isinstance(target, ast.Name) and value:
                self.bindings[target.id] = value

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value:
            self.visit_Assign(ast.Assign(targets=[node.target], value=node.value))

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, (ast.Store, ast.Del)):
            self.bindings.pop(node.id, None)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        outer = self.bindings.copy()
        arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
        if node.args.vararg:
            arguments.append(node.args.vararg)
        if node.args.kwarg:
            arguments.append(node.args.kwarg)
        for default in [*node.args.defaults, *[d for d in node.args.kw_defaults if d]]:
            self.visit(default)
        for arg in arguments:
            self.bindings.pop(arg.arg, None)
        self.visit(node.body)
        self.bindings = outer

    def visit_ListComp(self, node: ast.ListComp | ast.SetComp | ast.GeneratorExp | ast.DictComp) -> None:
        outer = self.bindings.copy()
        for generator in node.generators:
            self.visit(generator.iter)
            self.visit(generator.target)
            for condition in generator.ifs:
                self.visit(condition)
        if isinstance(node, ast.DictComp):
            self.visit(node.key)
            self.visit(node.value)
        else:
            self.visit(node.elt)
        self.bindings = outer

    visit_SetComp = visit_ListComp
    visit_GeneratorExp = visit_ListComp
    visit_DictComp = visit_ListComp

    def visit_Call(self, node: ast.Call) -> None:
        name = self.resolve(node.func)
        if "app-http-client" in self.enabled and self.package != "app-http-client":
            if name in {"httpx.Client", "httpx.AsyncClient"}:
                getter = "get_http_client" if name.endswith("AsyncClient") else "get_http_sync_client"
                self.report(
                    node,
                    "ARCH_HTTP_CLIENT_CONSTRUCTION",
                    f"{name} bypasses shared client settings and lifecycle.",
                    f"Use app_http_client.{getter}(); suppress with a reason for an intentionally isolated client.",
                    "http",
                )
            if name in {"shared_async_client.aclose", "shared_sync_client.close"}:
                self.report(
                    node,
                    "ARCH_SHARED_CLIENT_CLOSE",
                    "Application code closes a shared HTTP client.",
                    "Let app_http_client lifespan own shutdown; closing here affects other users of the client.",
                    "http",
                )
        layer_module = self.path.stem in {"router", "routes", "service", "services"} or bool(
            {"api", "services"}.intersection(self.path.parts)
        )
        if (
            "app-layer-base" in self.enabled
            and layer_module
            and name
            in {
                "sqlalchemy.create_engine",
                "sqlalchemy.engine.create_engine",
                "sqlalchemy.ext.asyncio.create_async_engine",
                "sqlalchemy.ext.asyncio.async_sessionmaker",
                "sqlalchemy.orm.sessionmaker",
            }
        ):
            self.report(
                node,
                "ARCH_DB_FACTORY_IN_LAYER",
                "Router/service constructs its own DB engine or session factory.",
                "Inject the configured session through get_session; keep separate database lifecycles in infrastructure code.",
                "backend/session",
            )
        is_time_impl = (
            self.package == "app-layer-base" and self.path.name == "time_util.py" and self.path.parent.name == "utils"
        )
        if (
            "app-layer-base" in self.enabled
            and not is_time_impl
            and name
            in {
                "datetime.datetime.now",
                "datetime.datetime.utcnow",
                "datetime.datetime.today",
                "datetime.date.today",
            }
        ):
            self.report(
                node,
                "ARCH_DIRECT_CURRENT_TIME",
                f"{name} bypasses the shared clock utility.",
                "Use app_layer_base.utils.time_util.get_current_utc_time() for UTC instants or "
                "get_current_utc_date() for UTC dates. Preserve explicit local-time semantics; do not blindly replace them.",
                "backend/time",
            )
        self.generic_visit(node)

    def visit_With(self, node: ast.With | ast.AsyncWith) -> None:
        if "app-http-client" in self.enabled and self.package != "app-http-client":
            for item in node.items:
                if self.resolve(item.context_expr) in {"shared_async_client", "shared_sync_client"}:
                    self.report(
                        node,
                        "ARCH_SHARED_CLIENT_CLOSE",
                        "A context manager will close the shared HTTP client.",
                        "Use the shared client directly and let app_http_client lifespan own shutdown.",
                        "http",
                    )
        self.generic_visit(node)

    visit_AsyncWith = visit_With
