"""Text-mode stdout sentinels of the devkit output contract (docs/architecture/agent-output.md in devkit)."""

from __future__ import annotations

import json
from collections.abc import Iterable

import click

Value = str | int | bool | Iterable[str] | None


def _value(value: Value) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, str):
        return ",".join(value) or "-"
    if any(char.isspace() or char in '"\\[]' for char in value):
        return json.dumps(value, ensure_ascii=False)
    return value


def fact(kind: str, positional: Value = None, /, **fields: Value) -> str:
    """One ``[KIND: positional key=value ...]`` line; free text is written as a JSON string."""
    parts = [] if positional is None else [_value(positional)]
    parts.extend(f"{key}={_value(value)}" for key, value in fields.items())
    return f"[{kind}: {' '.join(parts)}]"


def echo_fact(kind: str, positional: Value = None, /, **fields: Value) -> None:
    click.echo(fact(kind, positional, **fields))
