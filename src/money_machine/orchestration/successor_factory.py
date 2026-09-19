"""Successor job creation with workflow boundary enforcement.

Session 03 Wave 4: create successor jobs transactionally with parent results,
enforcing the winner/successor boundary for MULTIPLY decisions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from typing import TYPE_CHECKING
from uuid import UUID

from money_machine.domain.enums import DecisionType, ProductLifecycleState
from money_machine.domain.events import EventName
from money_machine.domain.models.portfolio import PortfolioDecision
from money_machine.orchestration.transition_guard import require_successor_spawn

if TYPE_CHECKING:
    from money_machine.persistence.unit_of_work import UnitOfWork


class SuccessorFactory:
    """Create successor jobs in response to workflow events."""

    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    async def create_successors(
        self,
        *,
        event_name: EventName,
        workflow_id: UUID,
        parent_job_id: UUID | None,
        payload: dict[str, object] | None = None,
        occurred_at: datetime | None = None,
    ) -> tuple[UUID, ...]:
        """Create successor jobs for a workflow event (deferred extension point).

        CONTRACT (Wave 4):
        - WINNER_DETECTED is routed through dispatch_decision/create_multiply_successor.
        - All other events currently produce no successors (empty tuple).
        - Future: load event → successor mappings from config/workflows.yaml.

        See tests/unit/test_successor_boundary.py::test_create_successors_contract_no_jobs
        for the explicit contract test proving the current "no successors" behavior.

        Returns the IDs of created successor jobs (empty tuple for now).
        """
        if occurred_at is None:
            occurred_at = datetime.now(UTC)

        # WINNER_DETECTED is handled by dispatch_decision/create_multiply_successor.
        # Other events route here but produce no successors in Wave 4.
        # Future Wave: load admitted_events → successor_job_types from YAML config.
        return ()

    async def create_multiply_successor(
        self,
        *,
        decision: PortfolioDecision,
        parent_job_id: UUID,
        occurred_at: datetime | None = None,
    ) -> tuple[UUID, ...]:
        """Create a MULTIPLY successor workflow and initial job.

        This enforces the winner/successor boundary:
        - Parent workflow transitions to OBSERVING
        - Successor workflow starts at DEDUPE_CHECK in a new workflow_id
        - require_successor_spawn validates the boundary
        """
        if occurred_at is None:
            occurred_at = datetime.now(UTC)

        if decision.decision != DecisionType.MULTIPLY:
            return ()

        # Verify this is a legal successor spawn
        parent_workflow = await self.uow.workflows.get(decision.workflow_id)
        if parent_workflow is None:
            raise ValueError(f"parent workflow {decision.workflow_id} not found")

        # Validate successor spawn boundary
        successor_entry_state = require_successor_spawn(
            parent_state=ProductLifecycleState(parent_workflow.product_state),
            parent_workflow_id=decision.workflow_id,
            successor_workflow_id=decision.successor_workflow_id,  # type: ignore[arg-type]
        )

        # Transition parent workflow to OBSERVING (guarded)
        from money_machine.orchestration.transition_guard import require_product_transition

        current_state = ProductLifecycleState(parent_workflow.product_state)
        target_state = ProductLifecycleState.OBSERVING
        require_product_transition(current_state, target_state)

        parent_workflow.product_state = target_state.value
        parent_workflow.version += 1
        await self.uow.session.flush()

        # Create successor workflow
        successor_workflow_id = await self._create_successor_workflow(
            parent_workflow_id=decision.workflow_id,
            parent_decision_id=decision.decision_id,
            successor_workflow_id=decision.successor_workflow_id,  # type: ignore[arg-type]
            shop_id=parent_workflow.shop_id,
            successor_state=successor_entry_state,
        )

        # Create the initial successor job (BuildSlotJob -> DedupeJob path)
        # In a full implementation, this would create the appropriate entry job
        # based on the workflow configuration
        successor_job_id = await self._create_successor_entry_job(
            successor_workflow_id=successor_workflow_id,
            successor_spec_id=decision.successor_spec_id,  # type: ignore[arg-type]
            occurred_at=occurred_at,
        )

        # Emit SUCCESSOR_CREATED event
        dedupe_key = (
            f"SUCCESSOR_CREATED:{decision.decision_id}:{successor_workflow_id}:{successor_job_id}"
        )
        await self.uow.events.append(
            event_name=EventName.SUCCESSOR_CREATED,
            aggregate_type="product_specs",
            aggregate_id=decision.successor_spec_id,  # type: ignore[arg-type]
            workflow_id=successor_workflow_id,
            job_id=successor_job_id,
            payload={
                "parent_workflow_id": str(decision.workflow_id),
                "parent_decision_id": str(decision.decision_id),
            },
            dedupe_key=dedupe_key,
            occurred_at=occurred_at,
        )

        return (successor_job_id,)

    async def _create_successor_workflow(
        self,
        *,
        parent_workflow_id: UUID,
        parent_decision_id: UUID,
        successor_workflow_id: UUID,
        shop_id: UUID,
        successor_state: ProductLifecycleState,
    ) -> UUID:
        """Create a new workflow row for the successor and return its ID."""
        from money_machine.persistence.tables import WorkflowRun

        workflow = WorkflowRun(
            id=successor_workflow_id,
            shop_id=shop_id,
            workflow_type="ProductLifecycleWorkflow",
            workflow_version=1,
            product_state=successor_state.value,
            parent_workflow_id=parent_workflow_id,
            parent_decision_id=parent_decision_id,
            started_at=datetime.now(UTC),
            version=1,
        )
        self.uow.session.add(workflow)
        await self.uow.session.flush()
        return workflow.id

    async def _create_successor_entry_job(
        self,
        *,
        successor_workflow_id: UUID,
        successor_spec_id: UUID,
        occurred_at: datetime,
    ) -> UUID:
        """Create the initial job for the successor workflow.

        In a full implementation, this would be a DedupeJob created by BuildSlotJob.
        For Wave 4, we create a placeholder job to prove the boundary works.
        """
        from money_machine.persistence.tables import Job

        # Derive job ID deterministically from workflow and spec IDs
        job_id = self._derive_job_id(successor_workflow_id, successor_spec_id, "DedupeJob")
        job = Job(
            id=job_id,
            workflow_id=successor_workflow_id,
            job_type="DedupeJob",
            object_type="product_specs",
            object_id=successor_spec_id,
            owner_agent_id="A06",
            status="PENDING",
            input={"successor_spec_id": str(successor_spec_id)},
            success_contract={"output_model": "DedupeResult"},
            scheduled_at=occurred_at,
            attempt=0,
            max_attempts=3,
            idempotency_key=f"DEDUPE:{successor_spec_id}",
            side_effect_class="NONE",
            retry_class="SAFE",
            allowed_mode="simulation",
            version=1,
        )
        self.uow.session.add(job)
        await self.uow.session.flush()
        return job_id

    @staticmethod
    def _derive_job_id(workflow_id: UUID, spec_id: UUID, job_type: str) -> UUID:
        """Derive a deterministic job ID from workflow, spec, and job type.

        This ensures tests can assert exact job IDs without randomness.
        """
        # Create a stable hash from the inputs
        hash_input = f"{workflow_id}:{spec_id}:{job_type}".encode()
        hash_digest = sha256(hash_input).digest()[:16]

        # Convert to UUID (version 5-style deterministic UUID)
        return UUID(bytes=hash_digest)
