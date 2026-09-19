"""Event-driven successor spawn coordination.

Session 03 Wave 4: event dispatcher listens for workflow events and
coordinates successor job creation via the successor factory.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from money_machine.domain.enums import DecisionType
from money_machine.domain.events import EventName
from money_machine.domain.models.portfolio import PortfolioDecision
from money_machine.orchestration.successor_factory import SuccessorFactory
from money_machine.persistence.repositories.events import EventAppendError

if TYPE_CHECKING:
    from money_machine.persistence.unit_of_work import UnitOfWork


class EventDispatcher:
    """Dispatch events to successor creation and other workflow handlers."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.factory = SuccessorFactory(uow)

    async def dispatch(
        self,
        *,
        event_name: EventName,
        aggregate_type: str,
        aggregate_id: UUID,
        workflow_id: UUID | None,
        job_id: UUID | None,
        payload: dict[str, object] | None = None,
        occurred_at: datetime | None = None,
    ) -> tuple[UUID, ...]:
        """Dispatch one event and create any authorized successors.

        Returns the IDs of any successor jobs created.
        """
        if occurred_at is None:
            occurred_at = datetime.now(UTC)

        dedupe_key = self._dedupe_key(event_name, aggregate_id, workflow_id, job_id)

        # Append event to log (idempotent via dedupe key)
        event_already_existed = False
        try:
            await self.uow.events.append(
                event_name=event_name,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                workflow_id=workflow_id,
                job_id=job_id,
                payload=payload or {},
                dedupe_key=dedupe_key,
                occurred_at=occurred_at,
            )
        except EventAppendError:
            # Event already exists - this is idempotent dispatch
            existing = await self.uow.events.by_dedupe_key(dedupe_key)
            if existing is None:
                raise
            # Event already existed - do not create successors again
            # (would cause PK collision with deterministic IDs)
            event_already_existed = True

        # Only create successors if this is a NEW event
        # Idempotent dispatch (event_already_existed=True) skips successor creation
        # to avoid PK collisions with deterministic job IDs
        #
        # SUCCESSOR_CREATED must NOT spawn successors: the successor workflow already has
        # its entry job created via _create_successor_entry_job in create_multiply_successor.
        # Routing SUCCESSOR_CREATED through the event map would create a duplicate DedupeJob.
        if (
            event_already_existed
            or workflow_id is None
            or event_name == EventName.SUCCESSOR_CREATED
        ):
            return ()

        return await self.factory.create_successors(
            event_name=event_name,
            workflow_id=workflow_id,
            parent_job_id=job_id,
            payload=payload,
            occurred_at=occurred_at,
        )

    async def dispatch_decision(
        self,
        *,
        decision: PortfolioDecision,
        parent_job_id: UUID,
        occurred_at: datetime | None = None,
    ) -> tuple[UUID, ...]:
        """Dispatch a portfolio decision event and handle MULTIPLY successors.

        For MULTIPLY decisions, this creates the successor workflow and transitions
        the parent to OBSERVING.

        Idempotent: On re-entry/double-dispatch with the same decision, returns the
        existing successor job IDs without creating new successors. This prevents
        duplicate successor creation when the same decision is dispatched multiple times.
        """
        if occurred_at is None:
            occurred_at = datetime.now(UTC)

        # Check for existing SUCCESSOR_CREATED event to ensure idempotency
        # If the same decision was already dispatched and created a successor,
        # we must not create a duplicate. The dedupe key for SUCCESSOR_CREATED
        # is unique per decision_id + successor_workflow_id + successor_job_id.
        # However, we need to check before we know the successor_job_id.
        # Instead, check if WINNER_DETECTED already exists for this decision.
        winner_dedupe_key = self._dedupe_key(
            EventName.WINNER_DETECTED,
            decision.decision_id,
            decision.workflow_id,
            parent_job_id,
        )

        # Check if WINNER_DETECTED was already emitted for this decision
        existing_winner = await self.uow.events.by_dedupe_key(winner_dedupe_key)

        if existing_winner is not None and decision.decision == DecisionType.MULTIPLY:
            # This decision was already dispatched. Find the existing successor job.
            # The successor_job_id is deterministically derived in _create_successor_entry_job,
            # so we can look it up by querying jobs with the successor workflow_id.
            from money_machine.persistence.tables import Job

            if decision.successor_workflow_id:
                # Query for jobs in the successor workflow
                from sqlalchemy import select

                stmt = select(Job).where(Job.workflow_id == decision.successor_workflow_id).limit(1)
                result = await self.uow.session.execute(stmt)
                existing_job = result.scalars().first()

                if existing_job:
                    # Return the existing successor job ID(s) without creating new ones
                    return (existing_job.id,)

            # If we can't find the existing job but the event exists, return empty tuple
            # (safer than creating a duplicate)
            return ()

        # For MULTIPLY decisions, create the successor workflow and jobs FIRST
        # Wave 6: Emit WINNER_DETECTED only AFTER successful successor validation
        # This prevents orphan events when guard rejects (raises exception)
        successor_job_ids = await self.factory.create_multiply_successor(
            decision=decision,
            parent_job_id=parent_job_id,
            occurred_at=occurred_at,
        )

        # If we reach here, validation succeeded (even if no successor for non-MULTIPLY)
        # Emit WINNER_DETECTED for all decisions that pass validation
        event_name = EventName.WINNER_DETECTED
        dedupe_key = self._dedupe_key(
            event_name,
            decision.decision_id,
            decision.workflow_id,
            parent_job_id,
        )

        try:
            await self.uow.events.append(
                event_name=event_name,
                aggregate_type="decisions",
                aggregate_id=decision.decision_id,
                workflow_id=decision.workflow_id,
                job_id=parent_job_id,
                payload={"decision": decision.decision.value},
                dedupe_key=dedupe_key,
                occurred_at=occurred_at,
            )
        except EventAppendError:
            existing = await self.uow.events.by_dedupe_key(dedupe_key)
            if existing is None:
                raise

        # Wave 7: Emit SUCCESSOR_CREATED after WINNER_DETECTED (correct order)
        # Only for MULTIPLY decisions that actually created a successor
        if decision.decision == DecisionType.MULTIPLY and successor_job_ids:
            successor_job_id = successor_job_ids[0]
            successor_dedupe_key = (
                f"SUCCESSOR_CREATED:{decision.decision_id}:"
                f"{decision.successor_workflow_id}:{successor_job_id}"
            )

            try:
                await self.uow.events.append(
                    event_name=EventName.SUCCESSOR_CREATED,
                    aggregate_type="product_specs",
                    aggregate_id=decision.successor_spec_id,  # type: ignore[arg-type]
                    workflow_id=decision.successor_workflow_id,  # type: ignore[arg-type]
                    job_id=successor_job_id,
                    payload={
                        "parent_workflow_id": str(decision.workflow_id),
                        "parent_decision_id": str(decision.decision_id),
                    },
                    dedupe_key=successor_dedupe_key,
                    occurred_at=occurred_at,
                )
            except EventAppendError:
                # Idempotent: successor already created, check for existing event
                existing_successor = await self.uow.events.by_dedupe_key(successor_dedupe_key)
                if existing_successor is None:
                    raise

        return successor_job_ids

    @staticmethod
    def _dedupe_key(
        event_name: EventName,
        aggregate_id: UUID,
        workflow_id: UUID | None,
        job_id: UUID | None,
    ) -> str:
        """Generate a semantic dedupe key for this event."""
        parts = [
            event_name.value,
            str(aggregate_id),
            str(workflow_id) if workflow_id else "null",
            str(job_id) if job_id else "null",
        ]
        return ":".join(parts)
