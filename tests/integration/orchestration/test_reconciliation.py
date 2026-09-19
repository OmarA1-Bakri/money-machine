"""Integration tests for uncertain-effect reconciliation.

These tests use a real PostgreSQL database to verify the reconciliation workflow:
1. Job in UNCERTAIN_EXTERNAL_EFFECT
2. Query idempotency_records and effect_attempts
3. Call provider reconciler (fake for tests)
4. Record new effect_attempts row
5. Transition job to appropriate status

All tests use deterministic UUIDs (no uuid4) for reproducibility.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.enums import JobStatus, RetryClass, SideEffectClass
from money_machine.orchestration.idempotency import (
    get_latest_effect_attempt,
    record_effect_attempt,
    reserve_idempotency_key,
)
from money_machine.orchestration.reconciliation import (
    EffectState,
    FakeReconciler,
    ReconciliationBudgetExhausted,
    apply_reconciliation_result,
    reconcile_uncertain_effect,
)
from money_machine.persistence.tables import Job, WorkflowRun

# Deterministic UUIDs for tests (no uuid4)
JOB_ID_1 = UUID("00000000-0000-0000-0000-000000000001")
WORKFLOW_ID_1 = UUID("10000000-0000-0000-0000-000000000001")
OBJECT_ID_1 = UUID("20000000-0000-0000-0000-000000000001")
AGENT_RUN_ID_1 = UUID("30000000-0000-0000-0000-000000000001")


async def create_uncertain_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    idempotency_key: str,
    now: datetime,
) -> Job:
    """Helper to create a job in UNCERTAIN_EXTERNAL_EFFECT."""
    # Create workflow run first (foreign key requirement)
    workflow_run = WorkflowRun(
        id=WORKFLOW_ID_1,
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(workflow_run)
    await session.flush()

    # Now create the job
    job = Job(
        id=job_id,
        workflow_id=WORKFLOW_ID_1,
        job_type="PublishListingJob",
        object_type="EtsyListing",
        object_id=OBJECT_ID_1,
        owner_agent_id="A01",
        status=JobStatus.UNCERTAIN_EXTERNAL_EFFECT.value,
        input={},
        success_contract={},
        scheduled_at=now,
        attempt=0,
        max_attempts=3,
        idempotency_key=idempotency_key,
        side_effect_class=SideEffectClass.EXTERNAL_WRITE.value,
        retry_class=RetryClass.RECONCILE_FIRST.value,
        allowed_mode="simulation",
        created_at=now,
        updated_at=now,
    )
    session.add(job)
    await session.flush()
    return job


@pytest.mark.asyncio
async def test_reconcile_uncertain_effect_confirmed(session: AsyncSession) -> None:
    """Reconcile UNCERTAIN_EXTERNAL_EFFECT job to SUCCEEDED when effect is CONFIRMED."""
    now = datetime(2026, 9, 19, 2, 0, 0, tzinfo=UTC)
    idempotency_key = "test-key-1"

    # Create job
    await create_uncertain_job(session, job_id=JOB_ID_1, idempotency_key=idempotency_key, now=now)

    # Reserve idempotency key
    await reserve_idempotency_key(
        session,
        idempotency_key=idempotency_key,
        job_id=JOB_ID_1,
        operation="etsy.create_draft",
        side_effect_class=SideEffectClass.EXTERNAL_WRITE,
        now=now,
    )

    # Record initial uncertain effect
    await record_effect_attempt(
        session,
        idempotency_key=idempotency_key,
        job_id=JOB_ID_1,
        agent_run_id=AGENT_RUN_ID_1,
        provider="etsy",
        operation="etsy.create_draft",
        effect_state="UNKNOWN",
        provider_object_id=None,
        reconciliation_attempt=0,
        now=now,
    )

    # Reconcile with fake reconciler that returns CONFIRMED
    reconciler = FakeReconciler(
        effect_state=EffectState.CONFIRMED,
        provider_object_id="listing-123",
    )

    result = await reconcile_uncertain_effect(
        session,
        job_id=JOB_ID_1,
        reconciler=reconciler,
        max_reconciliation_attempts=3,
        now=now,
    )

    assert result.effect_state == EffectState.CONFIRMED
    assert result.next_job_status == JobStatus.SUCCEEDED
    assert result.reconciliation_attempt == 1
    assert result.provider_object_id == "listing-123"
    assert "CONFIRMED" in result.reason

    # Verify effect_attempts row was created
    latest = await get_latest_effect_attempt(session, idempotency_key=idempotency_key)
    assert latest is not None
    assert latest.reconciliation_attempt == 1
    assert latest.effect_state == "CONFIRMED"
    assert latest.provider_object_id == "listing-123"


@pytest.mark.asyncio
async def test_reconcile_uncertain_effect_absent(session: AsyncSession) -> None:
    """Reconcile UNCERTAIN_EXTERNAL_EFFECT job to FAILED when effect is ABSENT."""
    now = datetime(2026, 9, 19, 2, 0, 0, tzinfo=UTC)
    idempotency_key = "test-key-1"

    # Create job
    await create_uncertain_job(session, job_id=JOB_ID_1, idempotency_key=idempotency_key, now=now)

    # Reserve idempotency key
    await reserve_idempotency_key(
        session,
        idempotency_key=idempotency_key,
        job_id=JOB_ID_1,
        operation="etsy.create_draft",
        side_effect_class=SideEffectClass.EXTERNAL_WRITE,
        now=now,
    )

    # Record initial uncertain effect
    await record_effect_attempt(
        session,
        idempotency_key=idempotency_key,
        job_id=JOB_ID_1,
        agent_run_id=AGENT_RUN_ID_1,
        provider="etsy",
        operation="etsy.create_draft",
        effect_state="UNKNOWN",
        provider_object_id=None,
        reconciliation_attempt=0,
        now=now,
    )

    # Reconcile with fake reconciler that returns ABSENT
    reconciler = FakeReconciler(
        effect_state=EffectState.ABSENT,
        provider_object_id=None,
    )

    result = await reconcile_uncertain_effect(
        session,
        job_id=JOB_ID_1,
        reconciler=reconciler,
        max_reconciliation_attempts=3,
        now=now,
    )

    assert result.effect_state == EffectState.ABSENT
    assert result.next_job_status == JobStatus.FAILED
    assert result.reconciliation_attempt == 1
    assert result.provider_object_id is None
    assert "ABSENT" in result.reason

    # Verify effect_attempts row
    latest = await get_latest_effect_attempt(session, idempotency_key=idempotency_key)
    assert latest is not None
    assert latest.effect_state == "ABSENT"
    assert latest.provider_object_id is None


@pytest.mark.asyncio
async def test_reconcile_uncertain_effect_unknown_stays_uncertain(
    session: AsyncSession,
) -> None:
    """Reconcile UNCERTAIN_EXTERNAL_EFFECT stays uncertain if budget remains."""
    now = datetime(2026, 9, 19, 2, 0, 0, tzinfo=UTC)
    idempotency_key = "test-key-1"

    # Create job
    await create_uncertain_job(session, job_id=JOB_ID_1, idempotency_key=idempotency_key, now=now)

    # Reserve idempotency key
    await reserve_idempotency_key(
        session,
        idempotency_key=idempotency_key,
        job_id=JOB_ID_1,
        operation="etsy.create_draft",
        side_effect_class=SideEffectClass.EXTERNAL_WRITE,
        now=now,
    )

    # Record initial uncertain effect
    await record_effect_attempt(
        session,
        idempotency_key=idempotency_key,
        job_id=JOB_ID_1,
        agent_run_id=AGENT_RUN_ID_1,
        provider="etsy",
        operation="etsy.create_draft",
        effect_state="UNKNOWN",
        provider_object_id=None,
        reconciliation_attempt=0,
        now=now,
    )

    # Reconcile with fake reconciler that returns UNKNOWN
    reconciler = FakeReconciler(
        effect_state=EffectState.UNKNOWN,
        provider_object_id=None,
    )

    result = await reconcile_uncertain_effect(
        session,
        job_id=JOB_ID_1,
        reconciler=reconciler,
        max_reconciliation_attempts=3,
        now=now,
    )

    assert result.effect_state == EffectState.UNKNOWN
    assert result.next_job_status == JobStatus.UNCERTAIN_EXTERNAL_EFFECT
    assert result.reconciliation_attempt == 1
    assert "still UNKNOWN after 1 attempts" in result.reason


@pytest.mark.asyncio
async def test_reconcile_uncertain_effect_budget_exhausted(session: AsyncSession) -> None:
    """Reconcile moves to BLOCKED when reconciliation budget is exhausted."""
    now = datetime(2026, 9, 19, 2, 0, 0, tzinfo=UTC)
    idempotency_key = "test-key-1"

    # Create job
    await create_uncertain_job(session, job_id=JOB_ID_1, idempotency_key=idempotency_key, now=now)

    # Reserve idempotency key
    await reserve_idempotency_key(
        session,
        idempotency_key=idempotency_key,
        job_id=JOB_ID_1,
        operation="etsy.create_draft",
        side_effect_class=SideEffectClass.EXTERNAL_WRITE,
        now=now,
    )

    # Record initial uncertain effect
    await record_effect_attempt(
        session,
        idempotency_key=idempotency_key,
        job_id=JOB_ID_1,
        agent_run_id=AGENT_RUN_ID_1,
        provider="etsy",
        operation="etsy.create_draft",
        effect_state="UNKNOWN",
        provider_object_id=None,
        reconciliation_attempt=0,
        now=now,
    )

    # Reconcile twice more to reach attempt 2
    await record_effect_attempt(
        session,
        idempotency_key=idempotency_key,
        job_id=JOB_ID_1,
        agent_run_id=None,
        provider="etsy",
        operation="etsy.create_draft",
        effect_state="UNKNOWN",
        provider_object_id=None,
        reconciliation_attempt=1,
        now=now,
    )

    await record_effect_attempt(
        session,
        idempotency_key=idempotency_key,
        job_id=JOB_ID_1,
        agent_run_id=None,
        provider="etsy",
        operation="etsy.create_draft",
        effect_state="UNKNOWN",
        provider_object_id=None,
        reconciliation_attempt=2,
        now=now,
    )

    # Reconcile with fake reconciler that returns UNKNOWN (attempt 3, at budget)
    reconciler = FakeReconciler(
        effect_state=EffectState.UNKNOWN,
        provider_object_id=None,
    )

    result = await reconcile_uncertain_effect(
        session,
        job_id=JOB_ID_1,
        reconciler=reconciler,
        max_reconciliation_attempts=3,
        now=now,
    )

    assert result.effect_state == EffectState.UNKNOWN
    assert result.next_job_status == JobStatus.BLOCKED
    assert result.reconciliation_attempt == 3
    assert "reconciliation budget exhausted" in result.reason


@pytest.mark.asyncio
async def test_reconcile_raises_if_not_uncertain(session: AsyncSession) -> None:
    """reconcile_uncertain_effect raises ValueError if job is not UNCERTAIN_EXTERNAL_EFFECT."""
    now = datetime(2026, 9, 19, 2, 0, 0, tzinfo=UTC)
    idempotency_key = "test-key-1"

    # Create workflow run first
    workflow_run = WorkflowRun(
        id=WORKFLOW_ID_1,
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(workflow_run)
    await session.flush()

    # Create job in FAILED status
    job = Job(
        id=JOB_ID_1,
        workflow_id=WORKFLOW_ID_1,
        job_type="PublishListingJob",
        object_type="EtsyListing",
        object_id=OBJECT_ID_1,
        owner_agent_id="A01",
        status=JobStatus.FAILED.value,
        input={},
        success_contract={},
        scheduled_at=now,
        attempt=0,
        max_attempts=3,
        idempotency_key=idempotency_key,
        side_effect_class=SideEffectClass.EXTERNAL_WRITE.value,
        retry_class=RetryClass.SAFE.value,
        allowed_mode="simulation",
        created_at=now,
        updated_at=now,
    )
    session.add(job)
    await session.flush()

    # Reserve idempotency key
    await reserve_idempotency_key(
        session,
        idempotency_key=idempotency_key,
        job_id=JOB_ID_1,
        operation="etsy.create_draft",
        side_effect_class=SideEffectClass.EXTERNAL_WRITE,
        now=now,
    )

    reconciler = FakeReconciler(effect_state=EffectState.CONFIRMED)

    with pytest.raises(ValueError, match="expected UNCERTAIN_EXTERNAL_EFFECT"):
        await reconcile_uncertain_effect(
            session,
            job_id=JOB_ID_1,
            reconciler=reconciler,
            now=now,
        )


@pytest.mark.asyncio
async def test_apply_reconciliation_result_transitions_job(session: AsyncSession) -> None:
    """apply_reconciliation_result transitions job to determined status."""
    now = datetime(2026, 9, 19, 2, 0, 0, tzinfo=UTC)
    idempotency_key = "test-key-1"

    # Create job
    job = await create_uncertain_job(
        session, job_id=JOB_ID_1, idempotency_key=idempotency_key, now=now
    )

    assert job.status == JobStatus.UNCERTAIN_EXTERNAL_EFFECT.value

    # Apply reconciliation result that moves to SUCCEEDED
    from money_machine.orchestration.reconciliation import ReconciliationResult

    result = ReconciliationResult(
        effect_state=EffectState.CONFIRMED,
        next_job_status=JobStatus.SUCCEEDED,
        reconciliation_attempt=1,
        provider_object_id="listing-123",
        reason="test",
    )

    await apply_reconciliation_result(
        session,
        job_id=JOB_ID_1,
        result=result,
        now=now,
    )

    # Verify job status changed
    await session.refresh(job)
    assert job.status == JobStatus.SUCCEEDED.value


@pytest.mark.asyncio
async def test_reconcile_raises_if_budget_exceeded(session: AsyncSession) -> None:
    """reconcile_uncertain_effect raises ReconciliationBudgetExhausted if attempts > max."""
    now = datetime(2026, 9, 19, 2, 0, 0, tzinfo=UTC)
    idempotency_key = "test-key-1"

    # Create job
    await create_uncertain_job(session, job_id=JOB_ID_1, idempotency_key=idempotency_key, now=now)

    # Reserve idempotency key
    await reserve_idempotency_key(
        session,
        idempotency_key=idempotency_key,
        job_id=JOB_ID_1,
        operation="etsy.create_draft",
        side_effect_class=SideEffectClass.EXTERNAL_WRITE,
        now=now,
    )

    # Exhaust the budget (attempts 0, 1, 2, 3)
    for attempt in range(4):
        await record_effect_attempt(
            session,
            idempotency_key=idempotency_key,
            job_id=JOB_ID_1,
            agent_run_id=AGENT_RUN_ID_1 if attempt == 0 else None,
            provider="etsy",
            operation="etsy.create_draft",
            effect_state="UNKNOWN",
            provider_object_id=None,
            reconciliation_attempt=attempt,
            now=now,
        )

    # Next reconciliation should raise
    reconciler = FakeReconciler(effect_state=EffectState.UNKNOWN)

    with pytest.raises(ReconciliationBudgetExhausted, match="reconciliation budget exhausted"):
        await reconcile_uncertain_effect(
            session,
            job_id=JOB_ID_1,
            reconciler=reconciler,
            max_reconciliation_attempts=3,
            now=now,
        )
