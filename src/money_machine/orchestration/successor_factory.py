"""Successor job creation with workflow boundary enforcement.

Session 03 Wave 4: create successor jobs transactionally with parent results,
enforcing the winner/successor boundary for MULTIPLY decisions.
Session 03 Wave 7: YAML-driven event → successor job type mapping.
"""

from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

import yaml

from money_machine.domain.enums import DecisionType, ProductLifecycleState
from money_machine.domain.events import EventName
from money_machine.domain.models.portfolio import PortfolioDecision
from money_machine.orchestration.transition_guard import require_successor_spawn

if TYPE_CHECKING:
    from money_machine.persistence.unit_of_work import UnitOfWork


@lru_cache(maxsize=1)
def load_event_successor_map() -> dict[str, list[str]]:
    """Load the event → successor job types map from workflows.yaml.

    Returns a dict mapping event names to lists of successor job types.
    Cached for performance (config rarely changes during runtime).
    Fails closed: missing file or invalid structure raises an exception.
    """
    # Navigate from src/money_machine/orchestration/ up to repo root, then to config/
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "workflows.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Workflow configuration not found at {config_path}. Cannot determine event successors."
        )

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if not isinstance(config, dict):
        raise ValueError("workflows.yaml must contain a dict at root")

    event_map_raw = cast(Any, config.get("event_successor_map"))  # type: ignore[reportUnknownMemberType]
    if event_map_raw is None:
        raise ValueError(
            "workflows.yaml missing required 'event_successor_map' section. "
            "Cannot determine event successors."
        )

    if not isinstance(event_map_raw, dict):
        raise ValueError("event_successor_map must be a dict")

    # Validate structure and build typed result
    event_map: dict[str, list[str]] = {}

    for event_name_raw, successors_raw in cast(dict[Any, Any], event_map_raw).items():
        if not isinstance(event_name_raw, str):
            raise ValueError(f"Event name must be string, got {type(event_name_raw)}")

        if not isinstance(successors_raw, list):
            raise ValueError(
                f"Successors for {event_name_raw} must be a list, got {type(successors_raw)}"
            )

        successors: list[str] = []
        for job_type_raw in successors_raw:  # type: ignore[reportUnknownVariableType]
            if not isinstance(job_type_raw, str):
                raise ValueError(
                    f"Job type in successors for {event_name_raw} must be string, "
                    f"got {type(job_type_raw)}"  # type: ignore[reportUnknownArgumentType]
                )
            successors.append(job_type_raw)

        event_map[event_name_raw] = successors

    return event_map


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
        """Create successor jobs for a workflow event.

        CONTRACT (Wave 7):
        - Loads event → successor mappings from config/workflows.yaml
        - WINNER_DETECTED is still routed through dispatch_decision/create_multiply_successor
        - Unknown events (not in the map) fail closed with ValueError
        - Events mapped to empty list return empty tuple (no successors)
        - Creates all successor job types listed for the event

        Returns the IDs of created successor jobs.
        Raises ValueError if event is unknown (fail closed).
        """
        if occurred_at is None:
            occurred_at = datetime.now(UTC)

        # Load the event successor map
        successor_map = load_event_successor_map()

        # Fail closed: unknown events are rejected
        event_key = event_name.value
        if event_key not in successor_map:
            raise ValueError(
                f"Unknown event '{event_key}' not found in event_successor_map. "
                f"Cannot determine successors. Known events: {sorted(successor_map.keys())}"
            )

        successor_job_types = successor_map[event_key]

        # Empty list means no successors (valid, return empty tuple)
        if not successor_job_types:
            return ()

        # Create all successor jobs for this event
        created_job_ids: list[UUID] = []

        for job_type in successor_job_types:
            job_id = await self._create_successor_job(
                workflow_id=workflow_id,
                parent_job_id=parent_job_id,
                job_type=job_type,
                occurred_at=occurred_at,
            )
            created_job_ids.append(job_id)

        return tuple(created_job_ids)

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

        Wave 6: Defense in depth — guard enforced at TWO layers:
        1. Early check before helper call (fail-fast, prevents helper invocation)
        2. Guard inside _create_successor_workflow (prevents direct helper bypass)

        Additional validation:
        - Pydantic validation rejects same-workflow successors at construction
        """
        if occurred_at is None:
            occurred_at = datetime.now(UTC)

        if decision.decision != DecisionType.MULTIPLY:
            return ()

        # Verify this is a legal successor spawn
        parent_workflow = await self.uow.workflows.get(decision.workflow_id)
        if parent_workflow is None:
            raise ValueError(f"parent workflow {decision.workflow_id} not found")

        # Wave 6: Defense in depth — validate at caller AND helper
        # Early check rejects before helper call (fail-fast)
        current_state = ProductLifecycleState(parent_workflow.product_state)
        _successor_entry_state = require_successor_spawn(
            parent_state=current_state,
            parent_workflow_id=decision.workflow_id,
            successor_workflow_id=decision.successor_workflow_id,  # type: ignore[arg-type]
        )

        # Transition parent workflow to OBSERVING (guarded)
        from money_machine.orchestration.transition_guard import require_product_transition

        target_state = ProductLifecycleState.OBSERVING
        require_product_transition(current_state, target_state)

        parent_workflow.product_state = target_state.value
        parent_workflow.version += 1
        await self.uow.session.flush()

        # Create successor workflow
        # Wave 6: Guard also enforced inside _create_successor_workflow (defense in depth)
        successor_workflow_id = await self._create_successor_workflow(
            parent_workflow_id=decision.workflow_id,
            parent_state=current_state,
            parent_decision_id=decision.decision_id,
            successor_workflow_id=decision.successor_workflow_id,  # type: ignore[arg-type]
            shop_id=parent_workflow.shop_id,
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
        parent_state: ProductLifecycleState,
        parent_decision_id: UUID,
        successor_workflow_id: UUID,
        shop_id: UUID,
    ) -> UUID:
        """Create a new workflow row for the successor and return its ID.

        Wave 6: This helper ALWAYS calls require_successor_spawn before creating
        the successor workflow, so even a direct call to this private method
        cannot bypass the guard. The guard is the enforcement mechanism, not privacy.
        """
        # Wave 6: MANDATORY guard enforced at helper level
        # Validates parent state and cross-workflow boundary
        successor_entry_state = require_successor_spawn(
            parent_state=parent_state,
            parent_workflow_id=parent_workflow_id,
            successor_workflow_id=successor_workflow_id,
        )

        from money_machine.persistence.tables import WorkflowRun

        workflow = WorkflowRun(
            id=successor_workflow_id,
            shop_id=shop_id,
            workflow_type="ProductLifecycleWorkflow",
            workflow_version=1,
            product_state=successor_entry_state.value,
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

    async def _create_successor_job(
        self,
        *,
        workflow_id: UUID,
        parent_job_id: UUID | None,
        job_type: str,
        occurred_at: datetime,
    ) -> UUID:
        """Create a single successor job (Wave 7: placeholder implementation).

        In a full implementation, this would:
        - Look up the job definition from workflows.yaml
        - Determine object_type and object_id from the parent job or event payload
        - Set appropriate owner_agent_id, side_effect_class, retry_class, etc.
        - Create the Job row with all required fields

        For Wave 7, we create a minimal placeholder that proves the mapping works.
        The job details will be filled in by later waves when job creation is
        fully integrated with the workflow configuration.
        """
        from money_machine.persistence.tables import Job

        # Derive deterministic job ID
        job_id = self._derive_successor_job_id(
            workflow_id=workflow_id,
            parent_job_id=parent_job_id,
            job_type=job_type,
        )

        # Placeholder: create minimal job to prove the successor map works
        # Future: load full job spec from workflows.yaml
        job = Job(
            id=job_id,
            workflow_id=workflow_id,
            job_type=job_type,
            object_type="placeholder",  # Will be determined from workflow config
            object_id=workflow_id,  # Placeholder
            owner_agent_id="A01",  # Will be from workflow config
            status="PENDING",
            input={"parent_job_id": str(parent_job_id) if parent_job_id else None},
            success_contract={"output_model": "AgentResult"},
            scheduled_at=occurred_at,
            attempt=0,
            max_attempts=3,
            idempotency_key=f"{job_type}:{workflow_id}:{parent_job_id or 'none'}",
            side_effect_class="NONE",
            retry_class="SAFE",
            allowed_mode="simulation",
            version=1,
        )
        self.uow.session.add(job)
        await self.uow.session.flush()
        return job_id

    @staticmethod
    def _derive_successor_job_id(
        *,
        workflow_id: UUID,
        parent_job_id: UUID | None,
        job_type: str,
    ) -> UUID:
        """Derive a deterministic job ID for a successor job.

        Uses workflow ID, parent job ID, and job type to create a stable hash.
        This ensures tests can assert exact job IDs without randomness.
        """
        parent_str = str(parent_job_id) if parent_job_id else "none"
        hash_input = f"{workflow_id}:{parent_str}:{job_type}".encode()
        hash_digest = sha256(hash_input).digest()[:16]
        return UUID(bytes=hash_digest)

    @staticmethod
    def _derive_job_id(workflow_id: UUID, spec_id: UUID, job_type: str) -> UUID:
        """Derive a deterministic job ID from workflow, spec, and job type.

        This ensures tests can assert exact job IDs without randomness.
        (Legacy method for create_multiply_successor path)
        """
        # Create a stable hash from the inputs
        hash_input = f"{workflow_id}:{spec_id}:{job_type}".encode()
        hash_digest = sha256(hash_input).digest()[:16]

        # Convert to UUID (version 5-style deterministic UUID)
        return UUID(bytes=hash_digest)
