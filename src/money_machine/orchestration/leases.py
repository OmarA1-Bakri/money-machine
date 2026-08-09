"""Lease orchestration composed over the durable Task 3 repository."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from money_machine.domain.enums import JobState
from money_machine.orchestration.retry import retry_delay
from money_machine.persistence.database import Database
from money_machine.persistence.repositories.jobs import JobClaim
from money_machine.persistence.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class JobLease:
    job_id: UUID
    owner: str
    token: str
    attempt_number: int
    leased_at: datetime
    expires_at: datetime


class LeaseLostError(ValueError):
    """The database no longer recognizes this worker's live lease binding."""


class LeaseManager:
    """Compose public lease operations over one durable repository contract."""

    def __init__(self, database: Database, *, lease_ttl: timedelta) -> None:
        if lease_ttl <= timedelta(0):
            raise ValueError("lease_ttl must be positive")
        self._database = database
        self._lease_ttl = lease_ttl

    async def claim_next(self, owner: str, now: datetime) -> JobLease | None:
        normalized_owner = owner.strip()
        if not normalized_owner:
            raise ValueError("owner must not be empty")
        token = secrets.token_urlsafe(32)
        expires_at = now + self._lease_ttl
        async with UnitOfWork(self._database) as uow:
            await uow.jobs.enqueue_due_retries(now)
            claim = await uow.jobs.claim_next(
                owner=normalized_owner,
                token=token,
                now=now,
                expires_at=expires_at,
            )
        return None if claim is None else _lease_from_claim(claim)

    async def heartbeat(self, lease: JobLease, now: datetime) -> datetime:
        expires_at = now + self._lease_ttl
        async with UnitOfWork(self._database) as uow:
            claim = await _claim_for_lease(uow, lease)
            try:
                await uow.jobs.heartbeat(claim, now, expires_at)
            except ValueError as exc:
                raise ValueError("lease binding or expiry mismatch") from exc
        return expires_at

    async def mark_running(self, lease: JobLease, now: datetime) -> None:
        async with UnitOfWork(self._database) as uow:
            claim = await _claim_for_lease(uow, lease)
            await uow.jobs.mark_running(claim, now)

    async def fail(
        self,
        lease: JobLease,
        now: datetime,
        error_code: str,
        *,
        terminal: bool = False,
    ) -> str:
        del now  # Failure ownership and scheduling use one PostgreSQL statement clock.
        try:
            async with UnitOfWork(self._database) as uow:
                if uow.session is None:
                    raise RuntimeError("unit of work did not open a session")
                database_now = await uow.session.scalar(select(func.clock_timestamp()))
                if database_now is None:
                    raise RuntimeError("PostgreSQL did not return statement time")
                claim = await _claim_for_lease(uow, lease)
                if claim.job.state is JobState.LEASED:
                    await uow.jobs.mark_running(claim, database_now)
                    claim = JobClaim(
                        job=claim.job.model_copy(update={"state": JobState.RUNNING}),
                        owner=claim.owner,
                        token=claim.token,
                        attempt_number=claim.attempt_number,
                        leased_at=claim.leased_at,
                        expires_at=claim.expires_at,
                    )
                delay = (
                    None
                    if terminal
                    else retry_delay(
                        claim.job.retry_class,
                        claim.attempt_number,
                    )
                )
                retry_at = (
                    database_now + delay
                    if delay is not None and claim.attempt_number < claim.job.max_attempts
                    else None
                )
                await uow.jobs.fail_running(
                    claim,
                    now=database_now,
                    retry_at=retry_at,
                    error_code=error_code,
                )
        except ValueError as exc:
            raise LeaseLostError("lease binding or expiry mismatch") from exc
        return JobState.RETRY_WAIT.value if retry_at is not None else JobState.FAILED.value

    async def recover_expired(self, now: datetime) -> int:
        """Finalize expired attempts; due retries become READY on a later claim poll."""

        async with UnitOfWork(self._database) as uow:
            expired = await uow.jobs.list_expired(now)
            for claim in expired:
                delay = retry_delay(claim.job.retry_class, claim.attempt_number)
                retry_at = (
                    now + delay
                    if delay is not None and claim.attempt_number < claim.job.max_attempts
                    else None
                )
                await uow.jobs.recover_expired(claim, now=now, retry_at=retry_at)
        return len(expired)


def _lease_from_claim(claim: JobClaim) -> JobLease:
    return JobLease(
        job_id=claim.job.job_id,
        owner=claim.owner,
        token=claim.token,
        attempt_number=claim.attempt_number,
        leased_at=claim.leased_at,
        expires_at=claim.expires_at,
    )


async def _claim_for_lease(uow: UnitOfWork, lease: JobLease) -> JobClaim:
    job = await uow.jobs.get(lease.job_id)
    if job is None:
        raise ValueError("lease binding or expiry mismatch")
    return JobClaim(
        job=job,
        owner=lease.owner,
        token=lease.token,
        attempt_number=lease.attempt_number,
        leased_at=lease.leased_at,
        expires_at=lease.expires_at,
    )
