"""Lease-fenced, at-least-once event relay with short owned DB transactions."""

import asyncio
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from app_layer_base.base.schemas.event import DomainEvent
from app_layer_base.core.database.transaction import AsyncTransaction
from app_layer_base.utils.time_util import get_current_utc_time
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .models import EventStatus
from .policy import RelayOptions
from .repos import OutboxRepository


class EventPublisher(Protocol):
    """Return only after transport acknowledgement; retries reuse the event ID.

    Publishers must cooperate with asyncio cancellation and configure transport
    timeouts. Consumers must tolerate duplicates; a DB lease cannot fence an
    external side effect already in flight.
    """

    async def __call__(self, event_type: str, event: DomainEvent) -> None: ...


@dataclass
class RelayResult:
    claimed: int = 0
    published: int = 0
    retried: int = 0
    failed: int = 0
    lost: int = 0


@dataclass(frozen=True)
class _Claim:
    id: UUID
    token: UUID
    failures: int
    event_data: dict[str, Any]


class _PublishFailure(Exception):
    pass


class _LostClaim(Exception):
    pass


async def _cancel_and_drain(task: asyncio.Task) -> asyncio.CancelledError | None:
    """Drain the child and return any new owner cancellation for deferred propagation."""
    owner = asyncio.current_task()
    assert owner is not None
    cancelling = owner.cancelling()
    cancellation = None
    if not task.done() and not task.cancelling():
        task.cancel()
    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError as exc:
            # shield also raises when the child is cancelled. Only a new cancel
            # request on the owner must be propagated after cleanup completes.
            if owner.cancelling() > cancelling:
                cancellation = exc
                cancelling = owner.cancelling()
        except Exception:
            break
    if not task.cancelled():
        task.exception()  # Consume a failure even when the owner was cancelled.
    return cancellation


class OutboxRelay:
    def __init__(
        self,
        publisher: EventPublisher,
        *,
        session_maker: async_sessionmaker[AsyncSession] | None = None,
        options: RelayOptions | None = None,
        clock: Callable[[], datetime] = get_current_utc_time,
    ) -> None:
        self.publisher = publisher
        self.session_maker = session_maker
        self.options = options or RelayOptions()
        self.clock = clock
        self.repo = OutboxRepository()
        self._stopping = False

    def stop(self) -> None:
        """Stop claiming new work; an active publication can finish within its lease."""
        self._stopping = True

    def _now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("relay clock must return a timezone-aware datetime")
        return value.astimezone(UTC)

    async def _claim(self) -> _Claim | None:
        now, token = self._now(), uuid4()
        async with AsyncTransaction(self.session_maker) as session:
            row = await self.repo.claim_one(
                session,
                now=now,
                lease_expires_at=now + timedelta(seconds=self.options.lease_seconds),
                token=token,
            )
            if row is None:
                return None
            occurred = row.created_at
            if occurred.tzinfo is None:
                occurred = occurred.replace(tzinfo=UTC)
            # Detach all publication data before commit (also supports expire_on_commit=True).
            return _Claim(
                row.id,
                token,
                row.retry_count,
                {
                    "id": row.id,
                    "source": f"/{row.aggregate_type.lower()}/outbox",
                    "type": row.event_type,
                    "data": deepcopy(row.payload),
                    "time": occurred,
                    "meta": {"aggregate_type": row.aggregate_type, "aggregate_id": row.aggregate_id},
                },
            )

    async def _renew(self, claim: _Claim) -> bool:
        now = self._now()
        async with AsyncTransaction(self.session_maker) as session:
            return await self.repo.renew_claim(
                session,
                claim.id,
                claim.token,
                now=now,
                lease_expires_at=now + timedelta(seconds=self.options.lease_seconds),
            )

    async def _finish(self, claim: _Claim, *, error: str | None = None, exhausted: bool = False) -> EventStatus | None:
        now = self._now()
        failures = claim.failures + (1 if error and not exhausted else 0)
        status = (
            EventStatus.PUBLISHED
            if error is None
            else EventStatus.FAILED
            if exhausted or failures >= self.options.max_attempts
            else EventStatus.PENDING
        )
        async with AsyncTransaction(self.session_maker) as session:
            applied = await self.repo.finish_claim(
                session,
                claim.id,
                claim.token,
                now=now,
                status=status,
                retry_count=failures,
                next_attempt_at=self.options.retry_at(now, failures) if status == EventStatus.PENDING else None,
                error=error,
            )
        return status if applied else None

    async def _publish(self, claim: _Claim) -> None:
        # Validate after the claim commits so malformed persisted events consume
        # their retry budget instead of rolling back and blocking the queue head.
        try:
            event = DomainEvent.model_validate(claim.event_data)
        except ValidationError as exc:
            raise _PublishFailure("invalid_event") from exc
        task = asyncio.create_task(self.publisher(event.type, event))
        deadline = asyncio.get_running_loop().time() + self.options.publish_timeout_seconds
        try:
            while True:
                remaining = deadline - asyncio.get_running_loop().time()
                if remaining <= 0:
                    raise _PublishFailure("publish_timeout")
                done, _ = await asyncio.wait({task}, timeout=min(self.options.heartbeat_seconds, remaining))
                if done:
                    try:
                        task.result()
                    except Exception as exc:
                        # Do not persist transport exception messages, which can contain payloads/credentials.
                        raise _PublishFailure(type(exc).__name__) from exc
                    return
                if not await self._renew(claim):
                    raise _LostClaim
        finally:
            if cancellation := await _cancel_and_drain(task):
                raise cancellation

    async def run_once(self) -> RelayResult:
        """Process up to batch_size events, claiming each only when ready to publish.

        DB failures propagate; publisher failures are persisted as retries/FAILED.
        Cancellation leaves a lease for recovery; it never reports false success.
        """
        result = RelayResult()
        for _ in range(self.options.batch_size):
            if self._stopping:
                break
            claim = await self._claim()
            if claim is None:
                break
            result.claimed += 1
            if claim.failures >= self.options.max_attempts:
                status = await self._finish(claim, error="retry_budget_exhausted", exhausted=True)
            else:
                try:
                    await self._publish(claim)
                except _LostClaim:
                    result.lost += 1
                    continue
                except _PublishFailure as exc:
                    status = await self._finish(claim, error=str(exc))
                else:
                    status = await self._finish(claim)
            if status == EventStatus.PUBLISHED:
                result.published += 1
            elif status == EventStatus.PENDING:
                result.retried += 1
            elif status == EventStatus.FAILED:
                result.failed += 1
            else:
                result.lost += 1
        return result

    async def recover(self) -> RelayResult:
        """Requeue expired claims with backoff, or exhaust their failure budget."""
        result = RelayResult()
        for _ in range(self.options.batch_size):
            if self._stopping:
                break
            now = self._now()
            async with AsyncTransaction(self.session_maker) as session:
                status = await self.repo.recover_one(
                    session,
                    now=now,
                    legacy_threshold=now - timedelta(seconds=self.options.legacy_timeout_seconds),
                    max_attempts=self.options.max_attempts,
                    retry_schedule=self.options.retry_schedule(now),
                )
            if status is None:
                break
            if status == EventStatus.FAILED:
                result.failed += 1
            else:
                result.retried += 1
        return result

    async def requeue_failed(self, event_id: UUID) -> bool:
        """Explicit administrative replay. Never modifies an active claim."""
        async with AsyncTransaction(self.session_maker) as session:
            return await self.repo.requeue_failed(session, event_id, now=self._now())
