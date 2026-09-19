"""Orchestration engine: workflow operations and operator commands.

Session 03 gap-close: operator surface for starting workflows, retrying jobs, reconciling
uncertain effects, and running scheduler/worker cycles. Library functions only; no
production claim path exists (Exit 78 held).

This module provides the high-level orchestration operations that CLI and API consumers
invoke. All operations are transactional and use the dependency_resolver, scheduler, and
retry primitives.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from money_machine.domain.enums import JobStatus, RetryClass
from money_machine.orchestration.retry import evaluate_retry
from money_machine.orchestration.scheduler import run_scheduler_cycle
from money_machine.orchestration.transition_guard import require_job_transition
from money_machine.persistence.tables import EffectAttempt, Job, WorkflowRun

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class EngineError(Exception):
    """Base exception for orchestration engine operations."""


class WorkflowNotFoundError(EngineError):
    """Raised when a workflow cannot be found."""


class JobNotFoundError(EngineError):
    """Raised when a job cannot be found."""


class InvalidRetryError(EngineError):
    """Raised when a job cannot be retried."""


async def start_workflow(
    session: AsyncSession,
    *,
    workflow_type: str,
    product_state: str,
    shop_id: UUID,
    now: datetime,
) -> WorkflowRun:
    """Start a new workflow run.

    Creates a workflow_run record and returns it. The workflow's initial jobs
    should be created separately (by the successor_factory or workflow template).

    Args:
        session: Active database session
        workflow_type: The workflow template name
        product_state: Product lifecycle state this workflow operates on
        shop_id: The shop this workflow belongs to (required, NOT NULL)
        now: Current timestamp

    Returns:
        The created WorkflowRun record
    """
    workflow = WorkflowRun(
        workflow_type=workflow_type,
        workflow_version=1,  # Default version
        product_state=product_state,
        shop_id=shop_id,
        parent_workflow_id=None,
        started_at=now,
        completed_at=None,
    )

    session.add(workflow)
    await session.flush()
    return workflow


async def retry_failed_job(
    session: AsyncSession,
    *,
    job_id: UUID,
    now: datetime,
) -> Job:
    """Retry a FAILED job by transitioning it back to READY.

    Evaluates retry eligibility using the retry policy, then transitions
    FAILED → READY with updated scheduled_at per the backoff calculation.

    For RECONCILE_FIRST jobs: checks if reconciliation resolved the uncertain
    effect (ABSENT or CONFIRMED). If resolved, allows retry like IDEMPOTENT.

    Args:
        session: Active database session
        job_id: The FAILED job to retry
        now: Current timestamp

    Returns:
        The retried Job with status=READY

    Raises:
        JobNotFoundError: If the job doesn't exist
        InvalidRetryError: If the job cannot be retried
    """
    from sqlalchemy import select

    from money_machine.persistence.tables import EffectAttempt

    job = await session.get(Job, job_id, with_for_update=True)
    if job is None:
        raise JobNotFoundError(f"Job {job_id} not found")

    current_status = JobStatus(job.status)
    if current_status != JobStatus.FAILED:
        raise InvalidRetryError(f"Job is {current_status}, not FAILED")

    # Check if reconciliation has resolved (for RECONCILE_FIRST jobs)
    reconciliation_resolved = False
    if RetryClass(job.retry_class) == RetryClass.RECONCILE_FIRST:
        # Look for the most recent effect attempt
        statement = (
            select(EffectAttempt)
            .where(EffectAttempt.job_id == job_id)
            .order_by(EffectAttempt.reconciliation_attempt.desc())
            .limit(1)
        )
        result = await session.execute(statement)
        effect = result.scalars().first()

        # Reconciliation is resolved if effect_state is CONFIRMED or ABSENT
        if effect and effect.effect_state in ("CONFIRMED", "ABSENT"):
            reconciliation_resolved = True

    # Evaluate retry eligibility
    retry_class = RetryClass(job.retry_class)
    decision = evaluate_retry(
        retry_class=retry_class,
        current_attempt=job.attempt,
        max_attempts=job.max_attempts,
        now=now,
        reconciliation_resolved=reconciliation_resolved,
    )

    if not decision.can_retry:
        raise InvalidRetryError(f"Cannot retry: {decision.reason}")

    # Transition FAILED → READY
    require_job_transition(JobStatus.FAILED, JobStatus.READY)

    job.status = JobStatus.READY.value
    job.scheduled_at = decision.scheduled_at  # type: ignore[assignment]
    job.updated_at = now

    await session.flush()
    return job


async def cancel_workflow(
    session: AsyncSession,
    *,
    workflow_id: UUID,
    now: datetime,
) -> tuple[WorkflowRun, int]:
    """Cancel a workflow and all its pending/ready jobs.

    Marks the workflow as completed and transitions all PENDING/READY jobs to
    CANCELLED (they will not execute).

    Args:
        session: Active database session
        workflow_id: The workflow to cancel
        now: Current timestamp

    Returns:
        Tuple of (workflow, num_jobs_cancelled)

    Raises:
        WorkflowNotFoundError: If workflow doesn't exist
    """
    workflow = await session.get(WorkflowRun, workflow_id, with_for_update=True)
    if workflow is None:
        raise WorkflowNotFoundError(f"Workflow {workflow_id} not found")

    # Mark workflow complete
    workflow.completed_at = now

    # Cancel all PENDING and READY jobs (both can transition to CANCELLED)
    statement = (
        select(Job)
        .where(
            Job.workflow_id == workflow_id,
            Job.status.in_([JobStatus.PENDING.value, JobStatus.READY.value]),
        )
        .with_for_update()
    )

    result = await session.execute(statement)
    jobs = list(result.scalars().all())

    for job in jobs:
        current_status = JobStatus(job.status)
        require_job_transition(current_status, JobStatus.CANCELLED)
        job.status = JobStatus.CANCELLED.value
        job.updated_at = now

    await session.flush()
    return workflow, len(jobs)


async def reconcile_uncertain_effect(
    session: AsyncSession,
    *,
    job_id: UUID,
    effect_state: str,
    provider_object_id: str | None,
    now: datetime,
) -> EffectAttempt:
    """Reconcile an uncertain external effect after manual verification.

    Updates the effect_attempt record with the reconciliation outcome (CONFIRMED, ABSENT)
    and transitions the job status accordingly:
    - CONFIRMED → SUCCEEDED (effect was applied successfully)
    - ABSENT → FAILED (effect was not applied, job can retry)

    Args:
        session: Active database session
        job_id: The job with uncertain effect
        effect_state: Reconciliation outcome: CONFIRMED or ABSENT
        provider_object_id: Provider's object ID if CONFIRMED, None if ABSENT
        now: Current timestamp

    Returns:
        The updated EffectAttempt record

    Raises:
        JobNotFoundError: If job not found
        EngineError: If no effect attempt exists or effect_state invalid
    """
    if effect_state not in ("CONFIRMED", "ABSENT"):
        raise EngineError(f"effect_state must be CONFIRMED or ABSENT, got {effect_state}")

    # Get the job
    job = await session.get(Job, job_id, with_for_update=True)
    if job is None:
        raise JobNotFoundError(f"Job {job_id} not found")

    # Job must be in UNCERTAIN_EXTERNAL_EFFECT status
    current_status = JobStatus(job.status)
    if current_status != JobStatus.UNCERTAIN_EXTERNAL_EFFECT:
        raise EngineError(f"Job {job_id} is {current_status}, expected UNCERTAIN_EXTERNAL_EFFECT")

    # Find the most recent effect attempt for this job
    statement = (
        select(EffectAttempt)
        .where(EffectAttempt.job_id == job_id)
        .order_by(EffectAttempt.reconciliation_attempt.desc())
        .limit(1)
    )

    result = await session.execute(statement)
    effect = result.scalars().first()

    if effect is None:
        raise EngineError(f"No effect attempt found for job {job_id}")

    # Update effect record with reconciliation outcome
    effect.effect_state = effect_state
    effect.provider_object_id = provider_object_id
    effect.observed_at = now

    # Transition job status based on reconciliation outcome
    # CONFIRMED → SUCCEEDED (effect was applied), ABSENT → FAILED (allows retry)
    target_status = JobStatus.SUCCEEDED if effect_state == "CONFIRMED" else JobStatus.FAILED

    require_job_transition(current_status, target_status)
    job.status = target_status.value
    job.updated_at = now

    await session.flush()
    return effect


async def run_scheduler_once(
    session: AsyncSession,
    *,
    now: datetime,
) -> dict[str, int]:
    """Run one scheduler cycle manually.

    Useful for operator commands or testing. Promotes due jobs, reclaims expired
    leases, and detects stalled jobs.

    Args:
        session: Active database session (must be in a transaction)
        now: Current timestamp

    Returns:
        Dictionary with counts: promoted, reclaimed, stalled
    """
    return await run_scheduler_cycle(session, now=now)


async def run_worker_once(
    session: AsyncSession,
    *,
    worker_id: str,
    now: datetime,
) -> Job | None:
    """Claim one ready job for a worker (library only, fail-closed).

    This is the worker claim operation, but it remains fail-closed: it can be
    called from tests, but the worker process still exits 78.

    Args:
        session: Active database session
        worker_id: Worker identifier
        now: Current timestamp

    Returns:
        The claimed Job, or None if no work available
    """
    from datetime import timedelta

    from money_machine.orchestration.leases import claim_ready_job

    return await claim_ready_job(
        session,
        worker_id=worker_id,
        now=now,
        lease_duration=timedelta(minutes=5),
    )
