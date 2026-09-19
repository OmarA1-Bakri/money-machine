"""Dependency resolution for job promotion: PENDING → READY when conditions are met.

Session 03 wave 1 / gap-close: real implementation of dependency evaluation. A PENDING job
may transition to READY only when:

1. All predecessor dependencies have succeeded (satisfied_at IS NOT NULL in job_dependencies)
2. The job's scheduled_at time has arrived (scheduled_at <= now)
3. The owning workflow is still active (workflow_runs.completed_at IS NULL)
4. No idempotency collision exists (idempotency_key not already reserved by another job)

Dependency failure propagates: if any predecessor fails terminally, dependent jobs transition
to BLOCKED per the workflow's failure contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import exists, select

from money_machine.domain.enums import JobStatus
from money_machine.orchestration.transition_guard import require_job_transition
from money_machine.persistence.tables import IdempotencyRecord, Job, JobDependency, WorkflowRun

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class DependencyResolutionError(Exception):
    """Raised when dependency resolution fails for a specific reason."""


class DependencyNotSatisfiedError(DependencyResolutionError):
    """Raised when a job cannot become ready because dependencies are not satisfied."""


class WorkflowInactiveError(DependencyResolutionError):
    """Raised when a job's workflow has completed or been cancelled."""


class IdempotencyCollisionError(DependencyResolutionError):
    """Raised when a job's idempotency key is already reserved by another job."""


async def check_dependencies_satisfied(
    session: AsyncSession,
    *,
    job_id: UUID,
) -> bool:
    """Check if all dependencies for a job are satisfied.

    A dependency is satisfied when:
    - The predecessor job has succeeded (status = SUCCEEDED)
    - The dependency record has satisfied_at set (NOT NULL)

    Args:
        session: Active database session
        job_id: The job to check dependencies for

    Returns:
        True if all dependencies are satisfied (or there are no dependencies),
        False otherwise
    """
    # Check if any dependency is unsatisfied (satisfied_at IS NULL)
    # If such a dependency exists, return False; otherwise True
    unsatisfied_exists = await session.scalar(
        select(exists().where(JobDependency.job_id == job_id, JobDependency.satisfied_at.is_(None)))
    )
    return not unsatisfied_exists


async def check_workflow_active(
    session: AsyncSession,
    *,
    workflow_id: UUID,
) -> bool:
    """Check if a workflow is still active.

    A workflow is active if it has not yet completed (completed_at IS NULL).

    Args:
        session: Active database session
        workflow_id: The workflow to check

    Returns:
        True if the workflow is active, False if completed
    """
    # Query returns completed_at value directly (datetime | None)
    completed_at = await session.scalar(
        select(WorkflowRun.completed_at).where(WorkflowRun.id == workflow_id)
    )
    # Active = completed_at is NULL
    return completed_at is None


async def check_idempotency_collision(
    session: AsyncSession,
    *,
    job_id: UUID,
    idempotency_key: str,
) -> bool:
    """Check if an idempotency key is already reserved by a different job.

    Args:
        session: Active database session
        job_id: The job attempting to reserve the key
        idempotency_key: The key to check

    Returns:
        True if collision exists (key is reserved by another job),
        False if no collision (key is free or reserved by this job)
    """
    reserved_by_other = await session.scalar(
        select(
            exists().where(
                IdempotencyRecord.idempotency_key == idempotency_key,
                IdempotencyRecord.job_id != job_id,
            )
        )
    )
    return reserved_by_other or False


async def evaluate_job_readiness(
    session: AsyncSession,
    *,
    job_id: UUID,
    now: datetime,
) -> tuple[bool, str]:
    """Evaluate whether a PENDING job is ready for execution.

    Checks all conditions for PENDING → READY transition:
    1. All dependencies satisfied
    2. scheduled_at <= now
    3. Workflow still active
    4. No idempotency collision

    Args:
        session: Active database session
        job_id: The PENDING job to evaluate
        now: Current timestamp

    Returns:
        Tuple of (is_ready, reason) where:
        - is_ready: True if all conditions met
        - reason: Human-readable explanation
    """
    # Fetch the job
    job = await session.get(Job, job_id)
    if job is None:
        return False, f"Job {job_id} not found"

    if JobStatus(job.status) != JobStatus.PENDING:
        return False, f"Job is {job.status}, not PENDING"

    # Check scheduled_at
    if job.scheduled_at > now:
        return False, f"Job scheduled for {job.scheduled_at}, now is {now}"

    # Check dependencies
    deps_satisfied = await check_dependencies_satisfied(session, job_id=job_id)
    if not deps_satisfied:
        return False, "Dependencies not satisfied"

    # Check workflow active
    workflow_active = await check_workflow_active(session, workflow_id=job.workflow_id)
    if not workflow_active:
        return False, "Workflow is no longer active"

    # Check idempotency collision
    if job.idempotency_key:
        collision = await check_idempotency_collision(
            session,
            job_id=job_id,
            idempotency_key=job.idempotency_key,
        )
        if collision:
            return False, f"Idempotency key {job.idempotency_key} already reserved"

    return True, "All conditions satisfied"


async def promote_pending_to_ready(
    session: AsyncSession,
    *,
    job_id: UUID,
    now: datetime,
) -> Job:
    """Promote a PENDING job to READY after validating all conditions.

    This is the atomic operation that transitions PENDING → READY. It validates
    all conditions and performs the transition in one transaction.

    Args:
        session: Active database session (must be in a transaction)
        job_id: The PENDING job to promote
        now: Current timestamp for updated_at

    Returns:
        The promoted Job row with status=READY

    Raises:
        DependencyNotSatisfiedError: If dependencies are not met
        WorkflowInactiveError: If workflow has completed
        IdempotencyCollisionError: If idempotency key is reserved
        InvalidTransitionError: If the state transition is not allowed
    """
    # Lock the job for update
    job = await session.get(Job, job_id, with_for_update=True)
    if job is None:
        raise DependencyResolutionError(f"Job {job_id} not found")

    current_status = JobStatus(job.status)
    if current_status != JobStatus.PENDING:
        raise DependencyResolutionError(f"Job is {current_status}, not PENDING")

    # Validate all conditions
    is_ready, reason = await evaluate_job_readiness(session, job_id=job_id, now=now)

    if not is_ready:
        # Determine appropriate exception type
        if "dependencies" in reason.lower():
            raise DependencyNotSatisfiedError(reason)
        if "workflow" in reason.lower():
            raise WorkflowInactiveError(reason)
        if "idempotency" in reason.lower():
            raise IdempotencyCollisionError(reason)
        raise DependencyResolutionError(reason)

    # Validate the transition
    require_job_transition(JobStatus.PENDING, JobStatus.READY)

    # Perform the transition
    job.status = JobStatus.READY.value
    job.updated_at = now

    await session.flush()
    return job


async def propagate_dependency_failure(
    session: AsyncSession,
    *,
    failed_job_id: UUID,
    now: datetime,
) -> list[UUID]:
    """Propagate failure to dependent jobs when a predecessor fails.

    When a job reaches TERMINAL_FAILURE, all jobs depending on it should be
    transitioned to BLOCKED (they can never execute).

    Args:
        session: Active database session
        failed_job_id: The job that failed terminally
        now: Current timestamp

    Returns:
        List of job IDs that were blocked
    """
    # Find all PENDING jobs that depend on the failed job
    statement = (
        select(Job)
        .join(JobDependency, JobDependency.job_id == Job.id)
        .where(
            JobDependency.depends_on_job_id == failed_job_id,
            Job.status == JobStatus.PENDING.value,
        )
        .with_for_update()
    )

    result = await session.execute(statement)
    dependent_jobs = list(result.scalars().all())

    blocked_job_ids: list[UUID] = []
    for job in dependent_jobs:
        # Validate PENDING → BLOCKED transition
        require_job_transition(JobStatus.PENDING, JobStatus.BLOCKED)
        job.status = JobStatus.BLOCKED.value
        job.updated_at = now
        blocked_job_ids.append(job.id)

    await session.flush()
    return blocked_job_ids


async def satisfy_dependency(
    session: AsyncSession,
    *,
    succeeded_job_id: UUID,
    now: datetime,
) -> int:
    """Mark a job's dependencies as satisfied after it succeeds.

    When a job succeeds, update all dependency records where this job is the
    predecessor, setting satisfied_at to now.

    Args:
        session: Active database session
        succeeded_job_id: The job that succeeded
        now: Timestamp to record in satisfied_at

    Returns:
        Number of dependencies satisfied
    """
    # Find all dependencies where this job is the predecessor
    statement = select(JobDependency).where(
        JobDependency.depends_on_job_id == succeeded_job_id,
        JobDependency.satisfied_at.is_(None),
    )

    result = await session.execute(statement)
    dependencies = list(result.scalars().all())

    for dep in dependencies:
        dep.satisfied_at = now

    await session.flush()
    return len(dependencies)
