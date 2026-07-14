import subprocess

# Lock files produce enormous, zero-signal diffs that crowd out real changes in an AI prompt.
EXCLUDE_PATHSPEC = ["--", ".", ":(exclude)uv.lock"]

STAGED = ["--cached"]
HEAD = ["HEAD"]
LAST_COMMIT = ["HEAD~1", "HEAD"]


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def ensure_repo() -> None:
    if _run(["git", "rev-parse", "--is-inside-work-tree"]).returncode != 0:
        raise RuntimeError("Not a git repository.")


def stage_all() -> None:
    result = _run(["git", "add", "."])
    if result.returncode != 0:
        raise RuntimeError(f"git add failed: {result.stderr.strip()}")


def get_diff(revision: list[str]) -> str:
    """Return the diff for the given revision args, excluding noisy paths.

    Raises ValueError when the diff is empty, RuntimeError when git itself fails.
    """
    result = _run(["git", "diff", *revision, *EXCLUDE_PATHSPEC])
    if result.returncode != 0:
        raise RuntimeError(f"git diff failed: {result.stderr.strip()}")

    diff = result.stdout.strip()
    if not diff:
        raise ValueError("No changes found.")

    return diff
