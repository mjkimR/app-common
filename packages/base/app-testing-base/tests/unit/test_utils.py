"""Unit tests for random and time test utilities."""

import uuid
from datetime import UTC, datetime

from app_testing_base.utils import (
    days_ago,
    days_later,
    hours_ago,
    hours_later,
    random_email,
    random_int,
    random_string,
    random_uuid,
    utc_now,
)


def test_random_string():
    s1 = random_string(8)
    s2 = random_string(8)
    assert len(s1) == 8
    assert s1 != s2

    prefixed = random_string(4, prefix="item_")
    assert prefixed.startswith("item_")
    assert len(prefixed) == 9


def test_random_email():
    email = random_email(domain="test.org", prefix="admin")
    assert email.startswith("admin_")
    assert email.endswith("@test.org")


def test_random_uuid():
    u = random_uuid()
    assert isinstance(u, uuid.UUID)


def test_random_int():
    val = random_int(10, 20)
    assert 10 <= val <= 20


def test_time_utils():
    now = utc_now()
    assert isinstance(now, datetime)
    assert now.tzinfo == UTC

    past_days = days_ago(2)
    assert past_days < now
    future_days = days_later(2)
    assert future_days > now

    past_hours = hours_ago(1)
    assert past_hours < now
    future_hours = hours_later(1)
    assert future_hours > now
