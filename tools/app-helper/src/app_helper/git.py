from __future__ import annotations

import subprocess

from app_error import Actor, AppError, Retry

# Lock files produce enormous, zero-signal diffs that crowd out real changes in an AI prompt.
EXCLUDE_PATHSPEC = ["--", ".", ":(exclude)uv.lock"]

STAGED = ["--cached"]
HEAD = ["HEAD"]
LAST_COMMIT = ["HEAD~1", "HEAD"]


class NotAGitRepoError(AppError, RuntimeError):
    code = "NOT_A_GIT_REPO"
    actor = Actor.USER
    retry = Retry.AFTER_FIX

    def __init__(self, message: str = "Not a git repository.") -> None:
        super().__init__(message, fix="git init")


class GitCommandError(AppError, RuntimeError):
    code = "GIT_COMMAND_FAILED"
    actor = Actor.TOOL
    retry = Retry.SAFE


class NoChangesFoundError(AppError, ValueError):
    code = "NO_CHANGES_FOUND"
    actor = Actor.USER
    retry = Retry.AFTER_FIX

    def __init__(self, message: str = "No changes found.") -> None:
        super().__init__(message, fix="git status")


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def ensure_repo() -> None:
    if _run(["git", "rev-parse", "--is-inside-work-tree"]).returncode != 0:
        raise NotAGitRepoError("Not a git repository.")


def stage_all() -> None:
    result = _run(["git", "add", "."])
    if result.returncode != 0:
        raise GitCommandError(f"git add failed: {result.stderr.strip()}", details=[result.stderr.strip()])


def get_diff(revision: list[str]) -> str:
    """Return the diff for the given revision args, excluding noisy paths.

    Raises NoChangesFoundError when the diff is empty, GitCommandError when git itself fails.
    """
    result = _run(["git", "diff", *revision, *EXCLUDE_PATHSPEC])
    if result.returncode != 0:
        raise GitCommandError(f"git diff failed: {result.stderr.strip()}", details=[result.stderr.strip()])

    diff = result.stdout.strip()
    if not diff:
        raise NoChangesFoundError("No changes found.")

    return diff
