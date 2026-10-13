"""Advisories of the `devkit app` commands; every code is prefixed `APP_`."""

from __future__ import annotations

from collections.abc import Sequence

from devkit.advisory import Actor, AdvisoryError, Level, Retry


class AppToolsError(AdvisoryError):
    """An error, warning or notice raised or returned by an app-tools library function."""


def warning(message: str, *details: object, code: str, fix: str | None = None) -> AppToolsError:
    return AppToolsError(message, *details, code=code, level=Level.WARNING, fix=fix)


def notice(message: str, *details: object, code: str, fix: str | None = None) -> AppToolsError:
    return AppToolsError(message, *details, code=code, level=Level.NOTICE, fix=fix)


def invalid_input(
    message: str,
    *details: object,
    code: str,
    fix: str | None = None,
    target_files: Sequence[str] | None = None,
) -> AppToolsError:
    return AppToolsError.invalid_input(message, *details, code=code, fix=fix, target_files=target_files)


def manifest_invalid(path: str, problem: object) -> AppToolsError:
    return invalid_input(f"Cannot read {path}: {problem}", code="APP_MANIFEST_INVALID", target_files=[path])


def unavailable(message: str, *details: object, code: str, retry_after: str | None = None) -> AppToolsError:
    """A remote service could not be reached; nothing changed and the command can run again later."""
    return AppToolsError(message, *details, code=code, actor=Actor.NONE, retry=Retry.SAFE, retry_after=retry_after)


def step_failed(command: Sequence[str], output: str, *, restored: Sequence[str] = ()) -> AppToolsError:
    """A tool the command runs failed; ``restored`` lists the files put back as they were."""
    tail = [line for line in output.strip().splitlines()[-20:] if line.strip()]
    details = [*tail, *(f"restored: {path}" for path in restored)]
    return AppToolsError(
        f"`{' '.join(command)}` failed.",
        *details,
        code="APP_STEP_FAILED",
        actor=Actor.DEVELOPER,
        retry=Retry.AFTER_FIX,
        what_to_report=f"The output of `{' '.join(command)}`.",
    )
