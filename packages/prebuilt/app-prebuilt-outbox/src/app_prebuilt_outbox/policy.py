"""Relay retry and lease configuration, independent of transport and database."""

import math
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class RelayOptions:
    batch_size: int = 10
    max_attempts: int = 3
    retry_base_seconds: float = 5
    retry_max_seconds: float = 300
    lease_seconds: float = 60
    heartbeat_seconds: float = 15
    publish_timeout_seconds: float = 300
    legacy_timeout_seconds: float = 3600
    shutdown_timeout_seconds: float = 30

    def __post_init__(self) -> None:
        if type(self.batch_size) is not int or self.batch_size <= 0:
            raise ValueError("batch_size must be a positive integer")
        if type(self.max_attempts) is not int or self.max_attempts <= 0:
            raise ValueError("max_attempts must be a positive integer")
        for value in (
            self.retry_base_seconds,
            self.retry_max_seconds,
            self.lease_seconds,
            self.heartbeat_seconds,
            self.publish_timeout_seconds,
            self.legacy_timeout_seconds,
            self.shutdown_timeout_seconds,
        ):
            if not math.isfinite(value) or not 0 < value <= 604800:
                raise ValueError("relay durations must be finite, positive and at most one week")
        if self.retry_base_seconds > self.retry_max_seconds:
            raise ValueError("retry_base_seconds must not exceed retry_max_seconds")
        if self.heartbeat_seconds >= self.lease_seconds / 2:
            raise ValueError("heartbeat_seconds must be less than half the lease")

    def retry_schedule(self, now: datetime) -> list[datetime]:
        """Finite exponential schedule; its last entry is the cap for later failures."""
        delays = [self.retry_base_seconds]
        while delays[-1] < self.retry_max_seconds and len(delays) < self.max_attempts:
            delays.append(min(delays[-1] * 2, self.retry_max_seconds))
        return [now + timedelta(seconds=delay) for delay in delays]

    def retry_at(self, now: datetime, failures: int) -> datetime:
        schedule = self.retry_schedule(now)
        return schedule[min(max(failures - 1, 0), len(schedule) - 1)]
