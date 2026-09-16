import datetime
from datetime import UTC


def get_current_utc_time() -> datetime.datetime:
    """Return a timezone-aware UTC instant; use for application wall-clock timestamps."""
    return datetime.datetime.now(UTC)


def get_current_utc_date() -> datetime.date:
    """Return the current calendar date in UTC, which may differ from the local date."""
    return get_current_utc_time().date()
