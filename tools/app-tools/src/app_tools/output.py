"""Text-mode stdout sentinels of the devkit output contract.

The contract is section 3 of ``docs/architecture/ARCH-08-1-agent-output.md`` in devkit. devkit renders a field
with ``devkit_dist.adapters.cli.field_value``; the rule is repeated here so app-tools keeps working with every
devkit-dist release its dependency range allows.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable

import click

Value = str | int | bool | Iterable[str] | None

# A value is bare unless it holds whitespace, a quote, a bracket, ``=`` or a backslash.
_BARE_VALUE = re.compile(r'[^\s"\[\]=\\]+')


def _value(value: Value) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, str):
        value = ",".join(value)
        if not value:
            return "-"
    return value if _BARE_VALUE.fullmatch(value) else json.dumps(value, ensure_ascii=False)


def fact(kind: str, positional: Value = None, /, **fields: Value) -> str:
    """One ``[KIND: positional key=value ...]`` line; free text is written as a JSON string."""
    parts = [] if positional is None else [_value(positional)]
    parts.extend(f"{key}={_value(value)}" for key, value in fields.items())
    return f"[{kind}: {' '.join(parts)}]"


def echo_fact(kind: str, positional: Value = None, /, **fields: Value) -> None:
    click.echo(fact(kind, positional, **fields))
