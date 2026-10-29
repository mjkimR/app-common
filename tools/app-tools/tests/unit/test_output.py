from __future__ import annotations

import pytest
from app_tools.output import fact


@pytest.mark.parametrize(
    ("value", "rendered"),
    [
        (None, "-"),
        ("", "-"),
        ([], "-"),
        (True, "yes"),
        (False, "no"),
        (3, "3"),
        ("src/app.py", "src/app.py"),
        (["a", "b"], "a,b"),
        ("two words", '"two words"'),
        ("tab\there", '"tab\\there"'),
        ("key=value", '"key=value"'),
        ('say "hi"', '"say \\"hi\\""'),
        ("[x]", '"[x]"'),
        ("back\\slash", '"back\\\\slash"'),
        (["a b", "c"], '"a b,c"'),
        ("한글", "한글"),
    ],
)
def test_field_values_follow_the_devkit_rule(value, rendered):
    assert fact("KIND", value=value) == f"[KIND: value={rendered}]"


def test_positional_and_fields():
    assert fact("UPDATE", "abc", ref="v1 x", dry_run=False) == '[UPDATE: abc ref="v1 x" dry_run=no]'
