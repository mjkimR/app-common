"""Slows down password guessing at the login endpoint.

An account's strength is its password's. What keeps guessing impractical is that a caller only gets a handful of
wrong attempts before it is locked out.
"""

from collections import deque
from dataclasses import dataclass, field

# Bounds memory under a flood of distinct callers; the oldest entries go first.
MAX_TRACKED_CALLERS = 10_000


@dataclass
class _Caller:
    failures: deque[float] = field(default_factory=deque)
    locked_until: float = 0.0


class FailedLoginThrottle:
    """Counts failed logins per caller in this process.

    State is per process, so with several workers a caller gets that many times the attempts; that is still a
    handful per window. A lockout rejects every login from the caller, right password or not: checking the
    password while locked out would let guessing go on.
    """

    def __init__(self, max_failures: int, window_seconds: int, lockout_seconds: int) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._callers: dict[str, _Caller] = {}

    def retry_after(self, caller: str, now: float) -> int | None:
        """Seconds the caller still has to wait, or None when it may try."""
        entry = self._callers.get(caller)
        if entry is None or entry.locked_until <= now:
            return None
        return max(1, int(entry.locked_until - now))

    def record_failure(self, caller: str, now: float) -> bool:
        """Note a failed login; True when this failure starts a lockout."""
        entry = self._callers.pop(caller, None) or _Caller()
        # Re-inserted last, so the dict stays ordered by most recent failure.
        self._callers[caller] = entry
        while entry.failures and entry.failures[0] <= now - self.window_seconds:
            entry.failures.popleft()
        entry.failures.append(now)
        while len(self._callers) > MAX_TRACKED_CALLERS:
            self._callers.pop(next(iter(self._callers)))
        if len(entry.failures) < self.max_failures:
            return False
        entry.failures.clear()
        entry.locked_until = now + self.lockout_seconds
        return True

    def reset(self) -> None:
        self._callers.clear()
