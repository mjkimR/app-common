"""Run project checks and tools with compact, recoverable output."""

from __future__ import annotations

import math
import tempfile
from pathlib import Path

import click

from app_tools.runner.execution import execute
from app_tools.runner.planning import TASKS, Step, plan_task, plan_tool


class RunCommand(click.Command):
    """Keep arguments after -- verbatim, including wrapper-looking options."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        if "--" in args:
            index = args.index("--")
            ctx.meta["forwarded"] = tuple(args[index + 1 :])
            args = args[:index]
        return super().parse_args(ctx, args)


@click.command(cls=RunCommand)
@click.argument("command", required=False)
@click.option("--path", "directory", type=click.Path(exists=True, file_okay=False, path_type=Path), default=".")
@click.option("--raw", is_flag=True, help="Print complete output instead of compact output.")
@click.option("--fix", is_flag=True, help="Apply fixes (lint only; npm requires a lint:fix script).")
@click.option(
    "--warn-after",
    type=click.FloatRange(min=0),
    default=60.0,
    show_default=True,
    help="Warn once per command after this many seconds; 0 disables warnings. Does not cancel commands.",
)
@click.option("--no-warn", is_flag=True, help="Disable runner duration warnings; overrides --warn-after.")
@click.pass_context
def run(
    ctx: click.Context, command: str | None, directory: Path, raw: bool, fix: bool, warn_after: float, no_warn: bool
) -> None:
    """Run lint/check/test, a tool, or -- COMMAND ARGS.

    Uses existing project manifests; no app-tools configuration is required.
    Pass tool arguments after --. Relative paths belong to --path (default: cwd).
    """
    if not math.isfinite(warn_after):
        raise click.BadParameter("must be a finite number", param_hint="--warn-after")
    forwarded = ctx.meta.get("forwarded", ())
    root = directory.resolve()
    if fix and command != "lint":
        raise click.UsageError("--fix is only supported by run lint")
    try:
        if command in TASKS:
            if forwarded:
                raise click.UsageError("Task arguments are not forwarded; use an individual tool after run")
            steps, skipped = plan_task(root, command, fix)
            for reason in skipped:
                click.echo(f"SKIP {reason}")
        elif command:
            steps = [plan_tool(root, command, forwarded)]
        elif forwarded:
            steps = [Step(root, forwarded, forwarded[0])]
        else:
            raise click.UsageError("Specify lint/check/test, a tool, or -- COMMAND ARGS")
    except (ValueError, OSError) as error:
        raise click.ClickException(str(error)) from error
    if not steps:
        raise click.ClickException("No runnable targets found")
    # OS temporary storage keeps logs out of source control without editing .gitignore.
    log_dir = Path(tempfile.mkdtemp(prefix="app-tools-run-"))
    codes = [execute(step, log_dir, raw, warn_after=0 if no_warn else warn_after) for step in steps]
    if len(steps) > 1:
        click.echo(f"Result: {sum(code == 0 for code in codes)} passed, {sum(code != 0 for code in codes)} failed")
    ctx.exit(codes[0] if len(codes) == 1 else int(any(codes)))
