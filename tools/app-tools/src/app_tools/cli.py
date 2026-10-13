"""`devkit app`: the app-common command group, mounted through the `devkit.commands` entry point.

Every command follows devkit's output contract: results on stdout as `[KIND: ...]` lines or one
JSON object under `--format json`, advisories on stderr, exit codes 0/1/2.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from devkit.core.cli import (
    FORMAT_OPTION,
    boundary,
    echo_json,
    echo_notices,
    exit_on_warnings,
    is_json,
    report_exit_code,
)

from app_tools.envspec import SETTINGS  # a table only; the settings modules load on use
from app_tools.output import echo_fact

PROJECT_OPTION = click.option(
    "--project",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=".",
    show_default=True,
    help="The project to inspect.",
)
SOURCE_OPTION = click.option(
    "--source",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Read the guides of this app-common checkout instead of the installed ones.",
)


@click.group("app")
@click.version_option(package_name="app-tools", message="[VERSION: %(package)s %(version)s]")
def cli() -> None:
    """app-common guides, dependency updates, scaffolding and local development links."""


# guide


@cli.group("guide")
def guide() -> None:
    """Read the app-common guides that apply to a project; no network, no package imports."""


def _guide_header(report) -> None:
    echo_fact("GUIDE", version=report.version, source=str(report.source), project=str(report.project))
    state = report.state
    for package in state.packages():
        echo_fact(
            "PACKAGE",
            package,
            declared=package in state.declared,
            locked=state.locked.get(package),
            installed=state.installed.get(package),
        )
    for ref in state.refs:
        echo_fact("REF", ref)


@guide.command("list")
@PROJECT_OPTION
@SOURCE_OPTION
@click.option("--all", "all_topics", is_flag=True, help="Include the guides of packages the project does not use.")
@FORMAT_OPTION
@boundary
def guide_list(project: Path, source: Path | None, all_topics: bool, output_format: str) -> None:
    """List the guide topics for the packages the project declares or installs."""
    from app_tools.guide import list_guides

    report = list_guides(project, checkout=source, all_topics=all_topics)
    if is_json(output_format):
        echo_json(report.to_dict())
        return
    _guide_header(report)
    for topic in report.topics:
        echo_fact("TOPIC", topic.topic, packages=topic.packages, path=str(topic.path))
    if not report.topics:
        echo_fact("OK", topics=0)
    echo_notices(report.notices)
    exit_on_warnings(report.notices)


@guide.command("show")
@click.argument("topic")
@PROJECT_OPTION
@SOURCE_OPTION
@FORMAT_OPTION
@boundary
def guide_show(topic: str, project: Path, source: Path | None, output_format: str) -> None:
    """Print one guide; setup guides of packages not installed yet are readable too."""
    from app_tools.guide import show_guide

    report, text = show_guide(project, topic, checkout=source)
    entry = report.topics[0]
    if is_json(output_format):
        echo_json({**report.to_dict(), "content": text})
        return
    echo_fact("DOCUMENT", entry.topic, path=str(entry.path), version=report.version)
    click.echo(text, nl=not text.endswith("\n"))
    echo_notices(report.notices)
    exit_on_warnings(report.notices)


# update


@cli.command("update")
@click.option("--ref", default="main", show_default=True, help="app-common branch, tag or full commit to pin.")
@click.option("--dry-run", is_flag=True, help="Report the changes without writing files or running uv.")
@click.option("--no-sync", is_flag=True, help="Update pyproject.toml and uv.lock only; skip uv sync and devkit sync.")
@FORMAT_OPTION
@boundary
def update(ref: str, dry_run: bool, no_sync: bool, output_format: str) -> None:
    """Pin every app-common dependency, and the devkit revision app-common pins, to one app-common commit."""
    from app_tools.update import update_project

    result = update_project(Path.cwd(), ref, dry_run=dry_run, sync=not no_sync)
    if is_json(output_format):
        echo_json(result.to_dict())
        return
    devkit_rev = (result.devkit or {}).get("rev")
    echo_fact("UPDATE", result.commit, ref=result.ref, devkit=devkit_rev, dry_run=result.dry_run)
    for change in result.changes:
        echo_fact("MANIFEST", str(change.path), app_common=change.app_common, devkit=change.devkit)
    for command in result.commands:
        echo_fact("PLANNED" if result.dry_run else "RAN", command)
    echo_notices(result.notices)
    exit_on_warnings(result.notices)


# dev


@cli.group("dev")
def dev() -> None:
    """Link a consumer's installed app-common packages to a local checkout, and restore them."""


def _echo_link_result(result, output_format: str) -> None:
    if is_json(output_format):
        echo_json(result.to_dict())
        return
    if result.root is not None:
        echo_fact("APP_COMMON", str(result.root))
    for action in result.actions:
        echo_fact(
            action.action.upper(),
            action.package,
            kind=action.kind,
            source=str(action.source) if action.source else None,
        )
    echo_fact("OK", changed=len(result.actions), dry_run=result.dry_run)
    echo_notices(result.notices)
    exit_on_warnings(result.notices)


TARGET_OPTION = click.option(
    "--target-path",
    "-t",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="The app-common checkout [default: found one directory level up or down].",
)


@dev.command("link")
@TARGET_OPTION
@click.option("--dry-run", is_flag=True, help="Report the links without changing the environment.")
@FORMAT_OPTION
@boundary
def dev_link(target_path: Path | None, dry_run: bool, output_format: str) -> None:
    """Replace installed app-common packages with symlinks into the checkout (backups kept as .bak)."""
    from app_tools.devlink import link

    _echo_link_result(link(Path.cwd(), target_path=target_path, dry_run=dry_run), output_format)


@dev.command("unlink")
@click.option("--dry-run", is_flag=True, help="Report the restorations without changing the environment.")
@FORMAT_OPTION
@boundary
def dev_unlink(dry_run: bool, output_format: str) -> None:
    """Restore every package `dev link` replaced from its .bak backup."""
    from app_tools.devlink import unlink

    _echo_link_result(unlink(Path.cwd(), dry_run=dry_run), output_format)


@dev.command("status")
@TARGET_OPTION
@FORMAT_OPTION
@boundary
def dev_status(target_path: Path | None, output_format: str) -> None:
    """Show which app-common packages are linked, installed or left inconsistent."""
    from app_tools.devlink import status

    result = status(Path.cwd(), target_path=target_path)
    if is_json(output_format):
        echo_json(result.to_dict())
    else:
        echo_fact("APP_COMMON", str(result.root) if result.root else None)
        for package in result.packages:
            echo_fact(
                "PACKAGE",
                package.package,
                kind=package.kind,
                state=package.state,
                target=str(package.target) if package.target else None,
                backup=package.backup,
            )
        for problem in result.problems:
            click.echo(problem.render(), err=True)
    sys.exit(report_exit_code(result.problems))


# doctor


@cli.command("doctor")
@PROJECT_OPTION
@FORMAT_OPTION
@boundary
def doctor(project: Path, output_format: str) -> None:
    """Check the project's app-common packages, the deployed devkit bundle and the database URL."""
    from app_tools.doctor import diagnose

    report = diagnose(project)
    if is_json(output_format):
        echo_json(report.to_dict())
    else:
        echo_fact(
            "DOCTOR",
            str(report.project),
            packages=report.packages,
            bundle=report.bundle,
            database=report.database,
        )
        for problem in report.problems:
            click.echo(problem.render(), err=True)
        echo_notices(report.notices)
    if not report.problems:
        exit_on_warnings(report.notices)
    sys.exit(report_exit_code(report.problems))


# create-code


@cli.group("create-code")
def create_code() -> None:
    """Scaffold app-common features from templates; existing files are never overwritten."""


def _scaffold_options(fn):
    fn = click.option("--dry-run", is_flag=True, help="Report the files without writing them.")(fn)
    fn = click.option("--prefix", help="The directory the feature is created under.")(fn)
    fn = click.option("--plural", help="The plural name in snake_case [default: derived from --name].")(fn)
    return click.option("--name", required=True, help="The feature name in CamelCase, for example Article.")(fn)


def _echo_feature(result, output_format: str) -> None:
    if is_json(output_format):
        echo_json(result.to_dict())
        return
    echo_fact(
        "FEATURE",
        result.feature,
        dir=str(result.feature_dir),
        files=len(result.files),
        router=result.router,
        dry_run=result.dry_run,
    )
    for path in result.files:
        echo_fact("PLANNED" if result.dry_run else "CREATED", str(path))
    echo_notices(result.notices)
    exit_on_warnings(result.notices)


@create_code.command("feature")
@_scaffold_options
@FORMAT_OPTION
@boundary
def create_feature_cmd(name: str, plural: str | None, prefix: str | None, dry_run: bool, output_format: str) -> None:
    """Create a backend CRUD feature (router, usecases, service, repository, schemas, tests) [prefix: app/features]."""
    from app_tools.create_code import create_feature

    result = create_feature(name, plural, Path.cwd(), prefix, dry_run=dry_run)
    _echo_feature(result, output_format)


@create_code.command("web-feature")
@_scaffold_options
@FORMAT_OPTION
@boundary
def create_web_feature_cmd(
    name: str, plural: str | None, prefix: str | None, dry_run: bool, output_format: str
) -> None:
    """Create a Svelte 5 web feature (state, view, dialog) [prefix: src/lib/features or web/src/lib/features]."""
    from app_tools.create_code import create_web_feature

    result = create_web_feature(name, plural, Path.cwd(), prefix, dry_run=dry_run)
    _echo_feature(result, output_format)


# env-spec


@cli.command("env-spec")
@click.option(
    "--type",
    "settings_type",
    required=True,
    type=click.Choice(list(SETTINGS)),
    help="The settings to describe.",
)
@FORMAT_OPTION
@boundary
def env_spec_cmd(settings_type: str, output_format: str) -> None:
    """List the environment variables an app-common settings class reads, with types and defaults."""
    from app_tools.envspec import env_spec

    variables = env_spec(settings_type)
    if is_json(output_format):
        echo_json({"type": settings_type, "variables": [variable.to_dict() for variable in variables]})
        return
    for variable in variables:
        echo_fact("ENV", variable.name, type=variable.type, default=variable.default)
    if not variables:
        echo_fact("OK", variables=0)
