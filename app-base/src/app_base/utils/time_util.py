import datetime
from datetime import UTC


def get_current_utc_time() -> datetime.datetime:
    """
    Returns the current UTC time.
    """
    return datetime.datetime.now(UTC)
