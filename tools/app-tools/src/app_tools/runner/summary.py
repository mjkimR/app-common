"""Extract bounded, recognizable tool summaries without changing their meaning."""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
MAX_SUMMARY = 2_000
MAX_WARNINGS = 2_000
MAX_WARNING_MESSAGE = 500
MAX_LINE = 1_000

_OUTCOME = r"\d+ (?:passed|failed|skipped|deselected|xfailed|xpassed|errors?|warnings?|rerun)"
_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        # pytest's normal/quiet terminal summary, including xdist and warning counts.
        rf"(?:{_OUTCOME}(?:, {_OUTCOME})*|no tests ran)(?: in \d+(?:\.\d+)?s(?: \([\d:]+\))?)?",
        # Vitest: preserve file counts separately from test counts.
        r"(?:Test Files|Tests)\s+\d+ (?:passed|failed|skipped|todo)"
        r"(?:\s*\|\s*\d+ (?:passed|failed|skipped|todo))*\s+\(\d+\)",
        # Playwright prints each outcome on its own line.
        r"\d+ (?:passed|failed|skipped|flaky|did not run)(?: \([\d.hms ]+\))?",
        # Ruff format/check, including --fix results.
        r"\d+ files? (?:reformatted|left unchanged|already formatted|would be reformatted)"
        r"(?:, \d+ files? (?:reformatted|left unchanged|already formatted|would be reformatted))*",
        r"All checks passed!",
        r"Found \d+ errors? \(\d+ fixed, \d+ remaining\)\.",
        # Pyright, svelte-check, and ESLint retain warning counts even on success.
        r"\d+ errors?, \d+ warnings?, \d+ informations?",
        r"svelte-check found \d+ errors? and \d+ warnings?(?: in \d+ files?)?",
        r"(?:✖\s+)?\d+ problems? \(\d+ errors?, \d+ warnings?\)",
        r"All matched files use Prettier code style!",
        # pytest-cov: label the total so the standalone line remains understandable.
        r"TOTAL\s+\d+\s+\d+(?:\s+\d+\s+\d+)?\s+\d+(?:\.\d+)?%",
    )
)
_WARNING_PATTERNS = tuple(
    re.compile(pattern)
    for pattern in (
        # Python/pytest and Pyright include the location on the same line.
        r"(?P<location>.+?:\d+(?::\d+)?): (?P<message>[\w.]*Warning: .+)",
        r"(?P<location>.+?:\d+:\d+) - warning: (?P<message>.+)",
        # Node runtime warnings include a process ID, which is not part of identity.
        r"\(node:\d+\) (?P<message>(?:\[[\w-]+\] )?[\w.]*Warning: .+)",
        # Ruff/uv and svelte-check use a one-line warning prefix.
        r"(?:warning|Warning|WARNING|Warn): (?P<message>.+)",
    )
)
_SOURCE_LOCATION = re.compile(r".+\.(?:svelte|[cm]?[jt]sx?|vue)(?::\d+:\d+)?")
_ESLINT_WARNING = re.compile(r"(?P<position>\d+:\d+)\s+warning\s+(?P<message>.+)")


def warning_message(line: str, source: str) -> tuple[str, str] | None:
    """Return message and first location for known one-line warning formats."""
    for pattern in _WARNING_PATTERNS:
        if match := pattern.fullmatch(line):
            location = match.groupdict().get("location") or (source if line.startswith("Warn:") else "")
            return " ".join(match["message"].split()), location
    if source and (match := _ESLINT_WARNING.fullmatch(line)):
        return " ".join(match["message"].split()), f"{source}:{match['position']}"
    return None


def summaries(log_path: Path) -> Iterator[str]:
    """Yield known summary lines in order; never infer counts from progress output.

    Match output rather than command names so npm scripts and shell wrappers work.
    Bound individual reads too: verbose tools may emit arbitrarily long lines.
    """
    remaining = MAX_SUMMARY
    warning_budget = MAX_WARNINGS
    seen_warnings: set[str] = set()
    source = ""
    with log_path.open(errors="replace") as stream:
        while line := stream.readline(MAX_LINE + 1):
            oversized = len(line) > MAX_LINE
            if oversized:
                prefix = line[:MAX_LINE]
                while line and not line.endswith("\n"):
                    line = stream.readline(MAX_LINE + 1)
                # A warning's prefix can still provide a useful short message.
                line = prefix
            clean = ANSI.sub("", line).strip().strip("=").strip()
            if not clean:
                source = ""
            elif _SOURCE_LOCATION.fullmatch(clean):
                source = clean
            if warning_budget >= 0 and (warning := warning_message(clean, source)):
                message, location = warning
                if message in seen_warnings:
                    continue
                seen_warnings.add(message)
                display = message
                if len(display) > MAX_WARNING_MESSAGE:
                    display = display[:MAX_WARNING_MESSAGE] + "..."
                display = f"WARN {display}" + (f" [{location}]" if location else "")
                if len(display) + 1 > warning_budget:
                    yield f"... warnings omitted; full log: {log_path}"
                    warning_budget = -1
                else:
                    yield display
                    warning_budget -= len(display) + 1
                continue
            if oversized or not any(pattern.fullmatch(clean) for pattern in _PATTERNS):
                continue
            if clean.startswith("TOTAL"):
                clean = f"Coverage: {clean}"
            if len(clean) + 1 > remaining:
                yield f"... summaries omitted; full log: {log_path}"
                return
            yield clean
            remaining -= len(clean) + 1
