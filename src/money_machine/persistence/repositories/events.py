"""Append-only domain event persistence."""

from __future__ import annotations

import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.events import DomainEvent
from money_machine.domain.value_objects import canonical_json
from money_machine.persistence.tables import domain_events


class EventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: DomainEvent) -> None:
        inserted = (
            await self._session.execute(
                pg_insert(domain_events)
                .values(
                    event_id=event.event_id,
                    workflow_run_id=event.workflow_run_id,
                    job_id=event.job_id,
                    name=event.name.value,
                    occurred_at=event.occurred_at,
                    payload=json.loads(canonical_json(event)),
                    payload_sha256=event.payload_sha256,
                )
                .on_conflict_do_nothing(index_elements=[domain_events.c.event_id])
                .returning(domain_events.c.event_id)
            )
        ).scalar_one_or_none()
        if inserted is not None:
            return
        existing = await self.get(event.event_id)
        if existing != event:
            raise ValueError(f"identity collision for {event.event_id}")

    async def get(self, event_id: UUID) -> DomainEvent | None:
        result = await self._session.execute(
            select(domain_events.c.payload).where(domain_events.c.event_id == event_id)
        )
        payload = result.scalar_one_or_none()
        return None if payload is None else DomainEvent.model_validate_json(json.dumps(payload))

    async def list_for_workflow(self, workflow_run_id: UUID) -> tuple[DomainEvent, ...]:
        result = await self._session.execute(
            select(domain_events.c.payload)
            .where(domain_events.c.workflow_run_id == workflow_run_id)
            .order_by(domain_events.c.occurred_at, domain_events.c.event_id)
        )
        return tuple(
            DomainEvent.model_validate_json(json.dumps(payload)) for payload in result.scalars()
        )
