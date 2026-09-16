"""Read bundled, versioned application guidance without network or package imports."""

from __future__ import annotations

import json
import re
import tomllib
from importlib.metadata import distributions
from pathlib import Path
from typing import Any

import click

BUNDLE = Path(__file__).resolve().parents[1] / "guide_data"


def read_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text) if path.suffix == ".json" else tomllib.loads(text)
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"Cannot read {path}: {exc}") from exc


def dependency_name(spec: str) -> str:
    match = re.match(r"[A-Za-z0-9_.-]+", spec)
    return re.sub(r"[-_.]+", "-", match[0]).lower() if match else ""


def inspect_project(root: Path, known: set[str]) -> dict[str, Any]:
    """Inspect only the selected project and its explicit uv workspace members."""
    manifest = read_manifest(root / "pyproject.toml")
    members = manifest.get("tool", {}).get("uv", {}).get("workspace", {})
    roots = {root}
    excludes = {p.resolve() for pattern in members.get("exclude", []) for p in root.glob(pattern)}
    for pattern in members.get("members", []):
        roots.update(p.resolve() for p in root.glob(pattern) if p.is_dir() and p.resolve() not in excludes)
    declared: dict[str, list[str]] = {}
    refs: set[str] = set()
    for folder in sorted(roots):
        doc = read_manifest(folder / "pyproject.toml")
        project = doc.get("project", {})
        specs = list(project.get("dependencies", []))
        for group in project.get("optional-dependencies", {}).values():
            specs.extend(group)
        for group in doc.get("dependency-groups", {}).values():
            specs.extend(spec for spec in group if isinstance(spec, str))
        for spec in specs:
            name = dependency_name(spec)
            if name in known:
                declared.setdefault(name, []).append(spec)
                match = re.search(r"app-common(?:\.git)?@([^#\s]+)", spec)
                if match:
                    refs.add(match[1])
        for name, source in doc.get("tool", {}).get("uv", {}).get("sources", {}).items():
            if dependency_name(name) not in declared:
                continue
            for entry in source if isinstance(source, list) else [source]:
                if isinstance(entry, dict) and "app-common" in entry.get("git", ""):
                    refs.add(entry.get("rev") or entry.get("tag") or entry.get("branch") or "un-pinned")
        for node_path in (folder / "package.json", folder / "web/package.json"):
            node = read_manifest(node_path)
            for group in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
                for name, spec in node.get(group, {}).items():
                    if name in known:
                        declared.setdefault(name, []).append(str(spec))
    locked: dict[str, str] = {}
    for package in read_manifest(root / "uv.lock").get("package", []):
        name = dependency_name(package.get("name", ""))
        if name in known:
            locked[name] = package.get("version", "unknown")
            git = package.get("source", {}).get("git")
            if git:
                refs.add(git)
    installed: dict[str, str] = {}
    paths = list((root / ".venv/lib").glob("python*/site-packages"))
    paths.append(root / ".venv/Lib/site-packages")
    for dist in distributions(path=[str(p) for p in paths if p.is_dir()]):
        name = dependency_name(dist.metadata.get("Name", ""))
        if name in known:
            installed[name] = dist.version
    for folder in roots:
        node = read_manifest(folder / "node_modules/@app-common/ui-base/package.json")
        if node:
            installed["@app-common/ui-base"] = node.get("version", "unknown")
        node = read_manifest(folder / "web/node_modules/@app-common/ui-base/package.json")
        if node:
            installed["@app-common/ui-base"] = node.get("version", "unknown")
    return {"declared": declared, "locked": locked, "installed": installed, "refs": sorted(refs)}


def report(context: dict[str, Any]) -> None:
    state = context["state"]
    version = context["catalog"]["version"]
    click.echo(f"Project: {context['project']}")
    click.echo(f"Guide version: {version}; source: {context['bundle']}")
    for label in ("declared", "locked", "installed"):
        values = state[label]
        summary = (
            ", ".join(f"{k}={v}" for k, v in sorted(values.items()))
            if label != "declared"
            else ", ".join(sorted(values))
        )
        click.echo(f"{label}: {summary or '(none detected)'}")
    click.echo("Dependency refs: " + (", ".join(state["refs"]) or "(not recorded)"))
    mismatches = {v for label in ("locked", "installed") for v in state[label].values() if v != version}
    mismatches.update(
        ref for ref in state["refs"] if re.fullmatch(r"v?\d+\.\d+\.\d+", ref) and ref.removeprefix("v") != version
    )
    if mismatches:
        click.echo("Warning: guide/package version mismatch: " + ", ".join(sorted(mismatches)))
    click.echo("Refs and optional/group declarations do not establish runtime availability or API compatibility.")


def list_topics(context: dict[str, Any], all_topics: bool) -> None:
    report(context)
    state = context["state"]
    packages = set(state["declared"]) | set(state["installed"])
    click.echo("\nGuides (use 'guide show <topic>'; 'guide list --all' includes uninstalled packages):")
    count = 0
    for topic, entry in context["catalog"]["guides"].items():
        if all_topics or packages.intersection(entry["packages"]):
            click.echo(f"  {topic}  [{', '.join(entry['packages'])}]")
            count += 1
    if not count:
        click.echo("  No matching dependencies detected. Use 'guide list --all' for setup guidance.")


@click.group(invoke_without_command=True)
@click.option("--project", type=click.Path(exists=True, file_okay=False, path_type=Path), default=".")
@click.option(
    "--source",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Use guides from this app-common checkout.",
)
@click.pass_context
def guide(ctx: click.Context, project: Path, source: Path | None) -> None:
    """Read local guidance; never fetch, sync, or import optional app packages."""
    bundle = source.resolve() / "tools/app-tools/src/app_tools/guide_data" if source else BUNDLE
    catalog = read_manifest(bundle / "catalog.json")
    if not catalog or not (bundle / "SKILL.md").is_file():
        raise click.ClickException(f"No guide bundle found at {bundle}.")
    known = {package for entry in catalog["guides"].values() for package in entry["packages"]}
    ctx.obj = {
        "bundle": bundle,
        "catalog": catalog,
        "project": project.resolve(),
        "state": inspect_project(project.resolve(), known),
    }
    if ctx.invoked_subcommand is None:
        list_topics(ctx.obj, False)


@guide.command("list")
@click.option("--all", "all_topics", is_flag=True, help="Include guides for packages not used by this project.")
@click.pass_obj
def guide_list(context: dict[str, Any], all_topics: bool) -> None:
    """List topics recommended for this project."""
    list_topics(context, all_topics)


@guide.command("show")
@click.argument("topic")
@click.pass_obj
def guide_show(context: dict[str, Any], topic: str) -> None:
    """Print one guide, including setup for packages not yet installed."""
    entry = context["catalog"]["guides"].get(topic)
    if entry is None:
        raise click.ClickException(f"Unknown guide '{topic}'. Use 'guide list --all'.")
    report(context)
    path = context["bundle"] / entry["path"]
    click.echo(f"\nDocument: {path}\nRelative links resolve from: {path.parent}\n")
    click.echo(path.read_text(encoding="utf-8"))
