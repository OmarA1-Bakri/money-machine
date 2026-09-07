"""Minimal row factories for database-backed tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.persistence.tables import (
    AgentDefinition,
    AgentRun,
    Artifact,
    EvidenceReference,
    Job,
    PromptVersion,
    Shop,
    WorkflowRun,
)

NOW = datetime(2026, 9, 7, 12, 0, tzinfo=UTC)
SHA = "b" * 64


async def make_shop(session: AsyncSession, name: str = "test-shop") -> Shop:
    """Insert one unconnected shop."""
    shop = Shop(id=uuid4(), name=name, connection_state="UNCONNECTED", timezone="UTC", active=True)
    session.add(shop)
    await session.flush()
    return shop


async def make_workflow(session: AsyncSession, shop: Shop) -> WorkflowRun:
    """Insert one workflow at the initial lifecycle state."""
    workflow = WorkflowRun(
        id=uuid4(),
        shop_id=shop.id,
        workflow_type="ProductLifecycleWorkflow",
        workflow_version=1,
        product_state="DISCOVERED",
        started_at=NOW,
        version=1,
    )
    session.add(workflow)
    await session.flush()
    return workflow


async def make_job(
    session: AsyncSession,
    workflow: WorkflowRun,
    *,
    idempotency_key: str | None = None,
    status: str = "READY",
    scheduled_at: datetime | None = None,
    attempt: int = 0,
    max_attempts: int = 3,
) -> Job:
    """Insert one durable job."""
    job = Job(
        id=uuid4(),
        workflow_id=workflow.id,
        job_type="ResearchCollectionJob",
        object_type="workflow_runs",
        object_id=workflow.id,
        owner_agent_id="A03",
        status=status,
        input={},
        success_contract={"output_model": "ResearchReport"},
        scheduled_at=scheduled_at or NOW,
        attempt=attempt,
        max_attempts=max_attempts,
        idempotency_key=idempotency_key or f"MARKET_RESEARCH_READ:{uuid4()}",
        side_effect_class="EXTERNAL_READ",
        retry_class="SAFE",
        allowed_mode="simulation",
        version=1,
    )
    session.add(job)
    await session.flush()
    return job


async def make_agent_run(session: AsyncSession, job: Job) -> AgentRun:
    """Insert one successful agent run carrying the lineage chain."""
    definition = AgentDefinition(
        id=uuid4(),
        agent_id="A03",
        name="Market Research",
        implementation_version=1,
        contract_version=1,
        default_side_effect_class="EXTERNAL_READ",
        default_retry_class="SAFE",
        timeout_seconds=600,
        commissioning_state="DESIGNED",
        commissioning_evidence=[],
    )
    prompt = PromptVersion(
        id=uuid4(),
        prompt_reference="prompt://A03/system",
        version=1,
        sha256=SHA,
        source_path="prompts/implementation/08_SESSION_05_MARKET_RESEARCH_TO_PRODUCT_SPEC.md",
    )
    session.add_all([definition, prompt])
    await session.flush()
    run = AgentRun(
        id=uuid4(),
        job_id=job.id,
        agent_definition_id=definition.id,
        agent_id="A03",
        agent_definition_version=1,
        prompt_version_id=prompt.id,
        prompt_reference=prompt.prompt_reference,
        prompt_sha256=SHA,
        status="SUCCESS",
        output={"rows": 30},
        error=None,
        started_at=NOW,
        completed_at=NOW + timedelta(seconds=5),
    )
    session.add(run)
    await session.flush()
    return run


async def make_artifact(
    session: AsyncSession,
    job: Job,
    run: AgentRun,
    *,
    logical_role: str = "listing_image",
) -> Artifact:
    """Insert one artifact attributed to a job and agent run."""
    artifact = Artifact(
        id=uuid4(),
        logical_role=logical_role,
        media_type="image/png",
        sha256=f"{uuid4().hex}{uuid4().hex}",
        byte_size=1024,
        storage_reference=f"artifact://{uuid4()}",
        producing_job_id=job.id,
        producing_agent_run_id=run.id,
        sensitivity="INTERNAL",
        retention_class="LINEAGE",
    )
    session.add(artifact)
    await session.flush()
    return artifact


async def make_evidence(
    session: AsyncSession,
    *,
    owner_type: str,
    owner_id: UUID,
    source_reference: str | None = None,
) -> EvidenceReference:
    """Insert one evidence citation for a result row."""
    evidence = EvidenceReference(
        id=uuid4(),
        owner_type=owner_type,
        owner_id=owner_id,
        evidence_type="provider-observation",
        source_reference=source_reference or f"receipt://{uuid4()}",
        safe_summary="Reconciled provider observation",
        observed_at=NOW,
    )
    session.add(evidence)
    await session.flush()
    return evidence


def money(amount: str) -> Decimal:
    """A decimal money amount."""
    return Decimal(amount)


def new_id() -> UUID:
    """A fresh identifier."""
    return uuid4()
