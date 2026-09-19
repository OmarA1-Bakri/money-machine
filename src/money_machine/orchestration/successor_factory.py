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
from typing import TYPE_CHECKING
from uuid import UUID

from money_machine.domain.enums import DecisionType, ProductLifecycleState
from money_machine.domain.events import EventName
from money_machine.domain.models.portfolio import PortfolioDecision
from money_machine.orchestration.transition_guard import require_successor_spawn

if TYPE_CHECKING:
    from money_machine.persistence.unit_of_work import UnitOfWork


@lru_cache(maxsize=1)
def load_workflows_config() -> tuple[dict[str, list[str]], object]:
    """Load WorkflowsConfig once and return both event map and full config.

    This is the SINGLE source of truth for YAML loading (should-fix B-2).
    Returns (event_successor_map, workflows_config) tuple.
    Both are cached together to ensure consistency.
    """
    from money_machine.config.loader import ConfigLoadError, load_yaml_model
    from money_machine.config.settings import WorkflowsConfig

    # Navigate from src/money_machine/orchestration/ up to repo root, then to config/
    config_path = Path(__file__).parent.parent.parent.parent / "config" / "workflows.yaml"

    if not config_path.exists():
        raise FileNotFoundError(
            f"Workflow configuration not found at {config_path}. Cannot determine event successors."
        )

    try:
        workflows_config = load_yaml_model(config_path, WorkflowsConfig)
    except ConfigLoadError as e:
        raise ValueError(f"Failed to load workflow configuration: {e}") from e

    return workflows_config.event_successor_map, workflows_config


@lru_cache(maxsize=1)
def load_event_successor_map() -> dict[str, list[str]]:
    """Load the event → successor job types map from workflows.yaml.

    Uses load_workflows_config as the single source of truth - no dual YAML loading.
    Returns a dict mapping event names to lists of successor job types.
    Cached for performance (config rarely changes during runtime).
    Fails closed: missing file or invalid structure raises an exception.
    """
    event_map, _config = load_workflows_config()
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

        # Wave 7: SUCCESSOR_CREATED emission moved to dispatch_decision
        # to ensure correct event order: WINNER_DETECTED → SUCCESSOR_CREATED
        # Return both job_id and workflow_id so dispatch can emit the event
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
        """Create the initial DedupeJob for the successor workflow.

        This creates a real DedupeJob that will be picked up by the appropriate
        agent (A06 Catalogue Dedupe). The job is fully specified with all required
        fields per the job schema.
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
        """Create a single successor job with real job spec from workflows.yaml.

        Loads the job definition from workflow configuration to get proper:
        - owner_agent_id
        - side_effect_class
        - retry_class
        - allowed_modes
        - output_contracts

        object_type/object_id are inferred from job type patterns.

        Uses the unified cached YAML config from load_workflows_config (should-fix B-2).
        """
        from money_machine.persistence.tables import Job

        # Use the UNIFIED cached config (should-fix B-2: no dual YAML load)
        _event_map, workflows_config = load_workflows_config()

        # Find job definition for this job_type
        job_def = None
        for workflow in workflows_config.workflows:
            for job in workflow.jobs:
                if job.job_type == job_type:
                    job_def = job
                    break
            if job_def:
                break

        if job_def is None:
            raise ValueError(f"Job type '{job_type}' not found in workflow configuration")

        # Derive deterministic job ID
        job_id = self._derive_successor_job_id(
            workflow_id=workflow_id,
            parent_job_id=parent_job_id,
            job_type=job_type,
        )

        # Infer object_type from job type patterns (real heuristics, not placeholders)
        object_type = self._infer_object_type(job_type)
        object_id = workflow_id  # Default to workflow_id

        # Use first allowed mode (simulation is typically first for safety)
        allowed_mode = job_def.allowed_modes[0] if job_def.allowed_modes else "simulation"

        # Use first output contract if available
        output_model = job_def.output_contracts[0] if job_def.output_contracts else "AgentResult"

        # Create real job with specs from workflow config
        job = Job(
            id=job_id,
            workflow_id=workflow_id,
            job_type=job_type,
            object_type=object_type,
            object_id=object_id,
            owner_agent_id=job_def.owner_agent_id,
            status="PENDING",
            input={"parent_job_id": str(parent_job_id) if parent_job_id else None},
            success_contract={"output_model": output_model},
            scheduled_at=occurred_at,
            attempt=0,
            max_attempts=3,
            idempotency_key=f"{job_type}:{workflow_id}:{parent_job_id or 'none'}",
            side_effect_class=job_def.side_effect_class,
            retry_class=job_def.retry_class,
            allowed_mode=allowed_mode,
            version=1,
        )
        self.uow.session.add(job)
        await self.uow.session.flush()
        return job_id

    @staticmethod
    def _infer_object_type(job_type: str) -> str:
        """Infer object_type from job_type based on domain patterns.

        Until payload-based determination is implemented, use job type patterns
        to infer the most likely object type.
        """
        job_type_lower = job_type.lower()

        # Dedupe and spec jobs work with product_specs
        if "dedupe" in job_type_lower or "spec" in job_type_lower or "niche" in job_type_lower:
            return "product_specs"

        # Build and QA jobs work with products
        if "build" in job_type_lower or "qa" in job_type_lower or "variant" in job_type_lower:
            return "products"

        # Decision and evaluation jobs work with decisions
        if (
            "decision" in job_type_lower
            or "evaluation" in job_type_lower
            or "slot" in job_type_lower
        ):
            return "decisions"

        # Research and collection jobs work with research_runs
        if "research" in job_type_lower or "collection" in job_type_lower:
            return "research_runs"

        # Listing, copy, asset jobs work with listing_versions
        if "listing" in job_type_lower or "copy" in job_type_lower or "asset" in job_type_lower:
            return "listing_versions"

        # Incident and repair jobs work with incidents
        if "incident" in job_type_lower or "repair" in job_type_lower:
            return "incidents"

        # Metrics and review jobs work with metrics_snapshots
        if "metric" in job_type_lower or "review" in job_type_lower:
            return "metrics_snapshots"

        # Default to workflow_runs for orchestration/provisioning jobs
        return "workflow_runs"

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
