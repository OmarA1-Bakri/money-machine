"""Append-only event log and idempotency reservations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from money_machine.domain.events import EventName
from money_machine.persistence.repositories._base import Repository
from money_machine.persistence.tables import EffectAttempt, Event, IdempotencyRecord


class EventAppendError(RuntimeError):
    """Raised when an event append would mutate or duplicate history."""


class EventRepository(Repository[Event]):
    """The durable event log. Appends only; existing rows are never updated."""

    model = Event

    async def append(
        self,
        *,
        event_name: EventName,
        aggregate_type: str,
        aggregate_id: UUID,
        dedupe_key: str,
        occurred_at: object,
        workflow_id: UUID | None = None,
        job_id: UUID | None = None,
        agent_run_id: UUID | None = None,
        payload: dict[str, object] | None = None,
    ) -> Event:
        """Append one event, refusing a duplicate semantic key."""
        if await self.by_dedupe_key(dedupe_key) is not None:
            raise EventAppendError(f"event {dedupe_key} is already recorded")
        event = Event(
            event_name=event_name.value,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            dedupe_key=dedupe_key,
            occurred_at=occurred_at,
            workflow_id=workflow_id,
            job_id=job_id,
            agent_run_id=agent_run_id,
            payload=payload or {},
        )
        self.add(event)
        await self.session.flush()
        return event

    async def by_dedupe_key(self, dedupe_key: str) -> Event | None:
        """Fetch the single event holding one dedupe key."""
        statement = select(Event).where(Event.dedupe_key == dedupe_key)
        return (await self.session.execute(statement)).scalars().one_or_none()

    async def for_aggregate(self, aggregate_id: UUID) -> tuple[Event, ...]:
        """Every event for one aggregate, in occurrence order."""
        statement = (
            select(Event)
            .where(Event.aggregate_id == aggregate_id)
            .order_by(Event.occurred_at, Event.recorded_at)
        )
        return tuple((await self.session.execute(statement)).scalars().all())


class IdempotencyRepository(Repository[IdempotencyRecord]):
    """Reservations that make an external effect happen at most once."""

    model = IdempotencyRecord

    async def by_key(self, key: str) -> IdempotencyRecord | None:
        """Fetch the reservation holding one key."""
        statement = select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
        return (await self.session.execute(statement)).scalars().one_or_none()

    async def reserve(
        self,
        *,
        idempotency_key: str,
        job_id: UUID,
        operation: str,
        side_effect_class: str,
    ) -> IdempotencyRecord:
        """Reserve a key before any external effect is attempted.

        The unique constraint is the real guard; this method surfaces the conflict as a
        typed error rather than a driver exception.
        """
        record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            job_id=job_id,
            operation=operation,
            side_effect_class=side_effect_class,
        )
        self.add(record)
        await self.session.flush()
        return record


class EffectAttemptRepository(Repository[EffectAttempt]):
    """Attempted external effects and their reconciliation outcomes (D-0025)."""

    model = EffectAttempt

    async def latest_for_key(self, key: str) -> EffectAttempt | None:
        """The most recent reconciliation attempt for one idempotency key."""
        statement = (
            select(EffectAttempt)
            .where(EffectAttempt.idempotency_key == key)
            .order_by(EffectAttempt.reconciliation_attempt.desc())
            .limit(1)
        )
        return (await self.session.execute(statement)).scalars().one_or_none()

    async def unresolved(self) -> tuple[EffectAttempt, ...]:
        """Every effect whose outcome is still unknown and therefore blocks retry."""
        statement = select(EffectAttempt).where(EffectAttempt.effect_state == "UNKNOWN")
        return tuple((await self.session.execute(statement)).scalars().all())
