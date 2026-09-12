"""Time and date test utilities for deterministic time offsets."""

from datetime import UTC, datetime, timedelta


def utc_now() -> datetime:
    """Return timezone-aware current UTC datetime."""
    return datetime.now(UTC)


def days_ago(days: int) -> datetime:
    """Return timezone-aware UTC datetime for N days in the past."""
    return utc_now() - timedelta(days=days)


def days_later(days: int) -> datetime:
    """Return timezone-aware UTC datetime for N days in the future."""
    return utc_now() + timedelta(days=days)


def hours_ago(hours: int) -> datetime:
    """Return timezone-aware UTC datetime for N hours in the past."""
    return utc_now() - timedelta(hours=hours)


def hours_later(hours: int) -> datetime:
    """Return timezone-aware UTC datetime for N hours in the future."""
    return utc_now() + timedelta(hours=hours)
