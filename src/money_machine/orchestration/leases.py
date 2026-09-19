"""Lease acquisition, heartbeat, expiry, and release primitives.

Session 03 wave 2: library primitives with deterministic concurrency tests. Worker and
scheduler remain fail-closed (exit 78); commissioning is Session 04.

These helpers implement the FOR UPDATE SKIP LOCKED pattern for exclusive job claiming,
lease lifecycle management (heartbeat, expiry, release), and deterministic worker IDs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select

from money_machine.domain.enums import JobStatus
from money_machine.persistence.tables import Job

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class LeaseAcquisitionError(Exception):
    """Raised when a lease cannot be acquired for a specific reason."""


class LeaseExpiredError(LeaseAcquisitionError):
    """Raised when attempting to operate on a lease that has expired."""


class LeaseNotHeldError(LeaseAcquisitionError):
    """Raised when attempting to release a lease not held by the worker."""


async def claim_ready_job(
    session: AsyncSession,
    *,
    worker_id: str,
    now: datetime,
    lease_duration: timedelta,
    limit: int = 1,
) -> Job | None:
    """Claim at most one ready job using FOR UPDATE SKIP LOCKED.

    Returns the claimed job on success, or None if no job was available. The job's
    status transitions READY -> RUNNING, and lease fields are populated atomically.

    Uses FOR UPDATE SKIP LOCKED to ensure exactly one worker claims each job even
    under concurrent access. Other workers skip locked rows and move to the next
    candidate.

    Args:
        session: Active database session for the transaction
        worker_id: Deterministic worker identifier (e.g., "worker-1")
        now: Current timestamp for lease_expires_at and heartbeat_at
        lease_duration: How long the lease is valid before expiry
        limit: Maximum jobs to consider (default 1)

    Returns:
        The claimed Job row with RUNNING status and lease fields set, or None
    """
    # Find ready jobs, oldest first, and lock exactly one
    statement = (
        select(Job)
        .where(
            Job.status == JobStatus.READY.value,
            Job.scheduled_at <= now,
        )
        .order_by(Job.scheduled_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )

    result = await session.execute(statement)
    job = result.scalars().first()

    if job is None:
        return None

    # Transition to RUNNING and set lease fields
    job.status = JobStatus.RUNNING.value
    job.lease_owner = worker_id
    job.lease_expires_at = now + lease_duration
    job.heartbeat_at = now
    job.updated_at = now

    await session.flush()
    return job


async def heartbeat(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    now: datetime,
) -> None:
    """Update the heartbeat timestamp for a leased job.

    Verifies the worker still holds the lease before updating. This is called
    periodically during job execution to prove the worker is still alive.

    Args:
        session: Active database session
        job_id: The job to heartbeat
        worker_id: The worker that should hold the lease
        now: Current timestamp

    Raises:
        LeaseExpiredError: If the lease has expired
        LeaseNotHeldError: If the worker doesn't hold the lease
    """
    statement = select(Job).where(Job.id == job_id).with_for_update()

    result = await session.execute(statement)
    job = result.scalars().one_or_none()

    if job is None:
        raise LeaseNotHeldError(f"Job {job_id} not found")

    if job.lease_owner != worker_id:
        raise LeaseNotHeldError(f"Job {job_id} is owned by {job.lease_owner}, not {worker_id}")

    if job.lease_expires_at is not None and job.lease_expires_at < now:
        raise LeaseExpiredError(f"Lease for job {job_id} expired at {job.lease_expires_at}")

    job.heartbeat_at = now
    job.updated_at = now
    await session.flush()


async def release_lease(
    session: AsyncSession,
    *,
    job_id: UUID,
    worker_id: str,
    now: datetime,
    final_status: JobStatus,
) -> None:
    """Gracefully release a lease and transition the job to its final status.

    Used when a job completes (SUCCEEDED/FAILED/TERMINAL_FAILURE) or is cancelled.
    The lease fields are cleared and the status is updated atomically.

    Args:
        session: Active database session
        job_id: The job to release
        worker_id: The worker that should hold the lease
        now: Current timestamp
        final_status: The status to transition to (e.g., SUCCEEDED, FAILED)

    Raises:
        LeaseNotHeldError: If the worker doesn't hold the lease
    """
    statement = select(Job).where(Job.id == job_id).with_for_update()

    result = await session.execute(statement)
    job = result.scalars().one_or_none()

    if job is None:
        raise LeaseNotHeldError(f"Job {job_id} not found")

    if job.lease_owner != worker_id:
        raise LeaseNotHeldError(f"Job {job_id} is owned by {job.lease_owner}, not {worker_id}")

    # Clear lease fields and transition to final status
    job.status = final_status.value
    job.lease_owner = None
    job.lease_expires_at = None
    job.heartbeat_at = None
    job.updated_at = now

    await session.flush()


async def reclaim_expired_leases(
    session: AsyncSession,
    *,
    now: datetime,
    limit: int = 50,
) -> tuple[Job, ...]:
    """Find and reset jobs with expired leases.

    Jobs are transitioned from RUNNING back to READY, and lease fields are cleared.
    This allows another worker to claim the job. Called by the scheduler or lease
    reaper process.

    Uses the partial index ix_jobs_lease_expiry for efficient queries.

    Args:
        session: Active database session
        now: Current timestamp to compare against lease_expires_at
        limit: Maximum jobs to reclaim in one call

    Returns:
        Tuple of jobs that were reclaimed and reset to READY
    """
    # Find expired leases
    statement = (
        select(Job)
        .where(
            Job.status == JobStatus.RUNNING.value,
            Job.lease_expires_at <= now,
        )
        .order_by(Job.lease_expires_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )

    result = await session.execute(statement)
    expired_jobs = tuple(result.scalars().all())

    # Reset each expired job to READY
    for job in expired_jobs:
        job.status = JobStatus.READY.value
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        job.updated_at = now

    await session.flush()
    return expired_jobs


def deterministic_worker_id(worker_index: int) -> str:
    """Generate a deterministic worker ID for testing.

    In production, worker IDs would typically be container IDs, pod names, or
    process IDs. For tests, we use deterministic sequential IDs to enable
    reproducible concurrency scenarios.

    Args:
        worker_index: Zero-based worker index (0, 1, 2, ...)

    Returns:
        A deterministic worker ID like "worker-0", "worker-1", etc.
    """
    return f"worker-{worker_index}"


def now_utc() -> datetime:
    """Current UTC timestamp, replacement for datetime.now(UTC) in tests."""
    return datetime.now(UTC)
