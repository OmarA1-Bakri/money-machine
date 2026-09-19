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
        if event_already_existed or workflow_id is None:
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
        """
        if occurred_at is None:
            occurred_at = datetime.now(UTC)

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
