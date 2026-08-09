"""Lease-bound transition validation through the durable job repository."""

from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.orchestration.leases import JobLease
from money_machine.persistence.repositories.jobs import JobClaim, JobRepository


class TransitionGuard:
    async def require_live_running_lease(
        self,
        session: AsyncSession,
        lease: JobLease,
        now: datetime,
    ) -> None:
        repository = JobRepository(session)
        job = await repository.get(lease.job_id)
        if job is None:
            raise ValueError("completion lease binding or expiry mismatch")
        claim = JobClaim(
            job=job,
            owner=lease.owner,
            token=lease.token,
            attempt_number=lease.attempt_number,
            leased_at=lease.leased_at,
            expires_at=lease.expires_at,
        )
        try:
            await repository.require_live_running(claim, now)
        except ValueError as exc:
            raise ValueError("completion lease binding or expiry mismatch") from exc


def require_same_job(expected: UUID, actual: UUID) -> None:
    if expected != actual:
        raise ValueError("handler outcome job mismatch")
