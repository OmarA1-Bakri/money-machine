"""Durable job persistence, leasing, and retry transitions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.enums import JobState
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.value_objects import canonical_json
from money_machine.persistence.tables import job_attempts, job_dependencies, jobs


@dataclass(frozen=True, slots=True)
class JobClaim:
    """Exact durable binding between one job attempt and one worker lease."""

    job: JobEnvelope
    owner: str
    token: str
    attempt_number: int
    leased_at: datetime
    expires_at: datetime


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        job: JobEnvelope,
        *,
        available_at: datetime | None = None,
        created_at: datetime | None = None,
    ) -> None:
        values = {
            "job_id": job.job_id,
            "workflow_run_id": job.workflow_run_id,
            "job_type": job.job_type,
            "state": job.state.value,
            "idempotency_key": job.idempotency_key,
            "input_sha256": job.input_sha256,
            "retry_class": job.retry_class.value,
            "max_attempts": job.max_attempts,
            "payload": json.loads(canonical_json(job)),
        }
        if available_at is not None:
            values["available_at"] = available_at
        if created_at is not None:
            values["created_at"] = created_at
            values["updated_at"] = created_at
        inserted = (
            await self._session.execute(
                pg_insert(jobs)
                .values(**values)
                .on_conflict_do_nothing(index_elements=[jobs.c.job_id])
                .returning(jobs.c.job_id)
            )
        ).scalar_one_or_none()
        if inserted is not None:
            return
        existing_payload = await self._session.scalar(
            select(jobs.c.payload).where(jobs.c.job_id == job.job_id)
        )
        if existing_payload is None:
            raise ValueError(f"identity collision for {job.job_id}")
        existing = JobEnvelope.model_validate_json(
            json.dumps(existing_payload, separators=(",", ":"))
        )
        if existing != job:
            raise ValueError(f"identity collision for {job.job_id}")

    async def add_dependency(self, job_id: UUID, depends_on_job_id: UUID) -> None:
        await self._session.execute(
            pg_insert(job_dependencies)
            .values(job_id=job_id, depends_on_job_id=depends_on_job_id)
            .on_conflict_do_nothing(
                index_elements=[
                    job_dependencies.c.job_id,
                    job_dependencies.c.depends_on_job_id,
                ]
            )
        )

    async def get(self, job_id: UUID) -> JobEnvelope | None:
        row = (
            await self._session.execute(
                select(jobs.c.payload, jobs.c.state).where(jobs.c.job_id == job_id)
            )
        ).one_or_none()
        return None if row is None else _job_from_row(row.payload, row.state)

    async def list_for_workflow(self, workflow_run_id: UUID) -> tuple[JobEnvelope, ...]:
        rows = (
            await self._session.execute(
                select(jobs.c.payload, jobs.c.state)
                .where(jobs.c.workflow_run_id == workflow_run_id)
                .order_by(jobs.c.created_at, jobs.c.job_id)
            )
        ).all()
        return tuple(_job_from_row(row.payload, row.state) for row in rows)

    async def claim_next(
        self,
        *,
        owner: str,
        token: str,
        now: datetime,
        expires_at: datetime,
    ) -> JobClaim | None:
        if not owner or not token or expires_at <= now:
            raise ValueError("claim requires owner, token, and future expiry")
        dependency_jobs = jobs.alias("claim_dependency_jobs")
        unsatisfied_dependency = (
            select(job_dependencies.c.depends_on_job_id)
            .join(
                dependency_jobs,
                dependency_jobs.c.job_id == job_dependencies.c.depends_on_job_id,
            )
            .where(
                job_dependencies.c.job_id == jobs.c.job_id,
                dependency_jobs.c.state != JobState.SUCCEEDED.value,
            )
            .exists()
        )
        row = (
            (
                await self._session.execute(
                    select(jobs)
                    .where(
                        jobs.c.state == JobState.READY.value,
                        jobs.c.available_at <= now,
                        ~unsatisfied_dependency,
                    )
                    .order_by(jobs.c.created_at, jobs.c.job_id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            return None
        attempt_number = int(row["attempt_count"]) + 1
        if attempt_number > int(row["max_attempts"]):
            raise ValueError("job has exhausted its bounded attempts")
        await self._session.execute(
            update(jobs)
            .where(jobs.c.job_id == row["job_id"], jobs.c.state == JobState.READY.value)
            .values(
                state=JobState.LEASED.value,
                attempt_count=attempt_number,
                lease_owner=owner,
                lease_token=token,
                leased_at=now,
                lease_expires_at=expires_at,
                updated_at=now,
            )
        )
        await self._session.execute(
            pg_insert(job_attempts).values(
                job_id=row["job_id"],
                attempt_number=attempt_number,
                state=JobState.LEASED.value,
                lease_token=token,
                started_at=now,
                payload={"lease_owner": owner},
            )
        )
        return JobClaim(
            job=_job_from_row(row["payload"], JobState.LEASED.value),
            owner=owner,
            token=token,
            attempt_number=attempt_number,
            leased_at=now,
            expires_at=expires_at,
        )

    async def mark_running(self, claim: JobClaim, now: datetime) -> None:
        await self._require_job_transition(
            claim,
            now=now,
            source=JobState.LEASED,
            target=JobState.RUNNING,
        )
        attempt = cast(
            CursorResult[Any],
            await self._session.execute(
                update(job_attempts)
                .where(
                    job_attempts.c.job_id == claim.job.job_id,
                    job_attempts.c.attempt_number == claim.attempt_number,
                    job_attempts.c.lease_token == claim.token,
                    job_attempts.c.state == JobState.LEASED.value,
                )
                .values(state=JobState.RUNNING.value)
            ),
        )
        if attempt.rowcount != 1:
            raise ValueError("job attempt lease mismatch")

    async def require_live_running(self, claim: JobClaim, now: datetime) -> None:
        matched = await self._session.scalar(
            select(jobs.c.job_id).where(
                jobs.c.job_id == claim.job.job_id,
                jobs.c.state == JobState.RUNNING.value,
                jobs.c.lease_owner == claim.owner,
                jobs.c.lease_token == claim.token,
                jobs.c.attempt_count == claim.attempt_number,
                jobs.c.lease_expires_at > now,
            )
        )
        if matched is None:
            raise ValueError("live running lease required")

    async def heartbeat(
        self,
        claim: JobClaim,
        now: datetime,
        expires_at: datetime,
    ) -> None:
        if expires_at <= now:
            raise ValueError("heartbeat expiry must be in the future")
        await self.require_live_running(claim, now)
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(jobs)
                .where(
                    jobs.c.job_id == claim.job.job_id,
                    jobs.c.state == JobState.RUNNING.value,
                    jobs.c.lease_owner == claim.owner,
                    jobs.c.lease_token == claim.token,
                    jobs.c.attempt_count == claim.attempt_number,
                    jobs.c.lease_expires_at > now,
                )
                .values(lease_expires_at=expires_at, updated_at=now)
            ),
        )
        if result.rowcount != 1:
            raise ValueError("heartbeat lease mismatch")

    async def fail_running(
        self,
        claim: JobClaim,
        *,
        now: datetime,
        retry_at: datetime | None,
        error_code: str,
    ) -> None:
        target = JobState.RETRY_WAIT if retry_at is not None else JobState.FAILED
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(jobs)
                .where(
                    jobs.c.job_id == claim.job.job_id,
                    jobs.c.state == JobState.RUNNING.value,
                    jobs.c.lease_owner == claim.owner,
                    jobs.c.lease_token == claim.token,
                    jobs.c.attempt_count == claim.attempt_number,
                    jobs.c.lease_expires_at > func.clock_timestamp(),
                )
                .values(
                    state=target.value,
                    available_at=retry_at if retry_at is not None else now,
                    lease_owner=None,
                    lease_token=None,
                    leased_at=None,
                    lease_expires_at=None,
                    updated_at=now,
                )
            ),
        )
        if result.rowcount != 1:
            raise ValueError("job failure lease mismatch")
        await self._finish_attempt(claim, now=now, error_code=error_code)

    async def enqueue_due_retries(self, now: datetime) -> int:
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(jobs)
                .where(
                    jobs.c.state == JobState.RETRY_WAIT.value,
                    jobs.c.available_at <= now,
                )
                .values(state=JobState.READY.value, updated_at=now)
            ),
        )
        return result.rowcount

    async def list_expired(self, now: datetime) -> tuple[JobClaim, ...]:
        rows = (
            (
                await self._session.execute(
                    select(jobs)
                    .where(
                        jobs.c.state.in_((JobState.LEASED.value, JobState.RUNNING.value)),
                        jobs.c.lease_expires_at <= now,
                    )
                    .order_by(jobs.c.lease_expires_at, jobs.c.job_id)
                    .with_for_update(skip_locked=True)
                )
            )
            .mappings()
            .all()
        )
        return tuple(_claim_from_row(row) for row in rows)

    async def recover_expired(
        self,
        claim: JobClaim,
        *,
        now: datetime,
        retry_at: datetime | None,
    ) -> None:
        target = JobState.RETRY_WAIT if retry_at is not None else JobState.FAILED
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(jobs)
                .where(
                    jobs.c.job_id == claim.job.job_id,
                    jobs.c.state.in_((JobState.LEASED.value, JobState.RUNNING.value)),
                    jobs.c.lease_owner == claim.owner,
                    jobs.c.lease_token == claim.token,
                    jobs.c.attempt_count == claim.attempt_number,
                    jobs.c.lease_expires_at <= now,
                )
                .values(
                    state=target.value,
                    available_at=retry_at if retry_at is not None else now,
                    lease_owner=None,
                    lease_token=None,
                    leased_at=None,
                    lease_expires_at=None,
                    updated_at=now,
                )
            ),
        )
        if result.rowcount != 1:
            raise ValueError("expired job lease mismatch")
        await self._finish_attempt(claim, now=now, error_code="EXPIRED_LEASE")

    async def activate_successor(self, parent_job_id: UUID, job_type: str) -> UUID:
        parent_state = await self._session.scalar(
            select(jobs.c.state).where(jobs.c.job_id == parent_job_id)
        )
        if parent_state != JobState.SUCCEEDED.value:
            raise ValueError("successor requires a succeeded predecessor")
        successor_id = await self._session.scalar(
            select(jobs.c.job_id)
            .join(job_dependencies, job_dependencies.c.job_id == jobs.c.job_id)
            .where(
                job_dependencies.c.depends_on_job_id == parent_job_id,
                jobs.c.job_type == job_type,
                jobs.c.state == JobState.PENDING.value,
            )
            .with_for_update()
        )
        if successor_id is None:
            raise ValueError("declared pending successor not found")
        dependency_jobs = jobs.alias("activation_dependency_jobs")
        unsatisfied_dependency = await self._session.scalar(
            select(job_dependencies.c.depends_on_job_id)
            .join(
                dependency_jobs,
                dependency_jobs.c.job_id == job_dependencies.c.depends_on_job_id,
            )
            .where(
                job_dependencies.c.job_id == successor_id,
                dependency_jobs.c.state != JobState.SUCCEEDED.value,
            )
            .limit(1)
        )
        if unsatisfied_dependency is not None:
            raise ValueError("successor has unsatisfied dependencies")
        await self._session.execute(
            update(jobs)
            .where(jobs.c.job_id == successor_id, jobs.c.state == JobState.PENDING.value)
            .values(state=JobState.READY.value)
        )
        return successor_id

    async def _require_job_transition(
        self,
        claim: JobClaim,
        *,
        now: datetime,
        source: JobState,
        target: JobState,
    ) -> None:
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(jobs)
                .where(
                    jobs.c.job_id == claim.job.job_id,
                    jobs.c.state == source.value,
                    jobs.c.lease_owner == claim.owner,
                    jobs.c.lease_token == claim.token,
                    jobs.c.attempt_count == claim.attempt_number,
                    jobs.c.lease_expires_at > now,
                )
                .values(state=target.value, updated_at=now)
            ),
        )
        if result.rowcount != 1:
            raise ValueError("job transition lease mismatch")

    async def _finish_attempt(
        self,
        claim: JobClaim,
        *,
        now: datetime,
        error_code: str,
    ) -> None:
        result = cast(
            CursorResult[Any],
            await self._session.execute(
                update(job_attempts)
                .where(
                    job_attempts.c.job_id == claim.job.job_id,
                    job_attempts.c.attempt_number == claim.attempt_number,
                    job_attempts.c.lease_token == claim.token,
                    job_attempts.c.state.in_((JobState.LEASED.value, JobState.RUNNING.value)),
                )
                .values(
                    state=JobState.FAILED.value,
                    completed_at=now,
                    error_code=error_code,
                )
            ),
        )
        if result.rowcount != 1:
            raise ValueError("job attempt lease mismatch")


def _job_from_row(payload: object, state: str) -> JobEnvelope:
    values = dict(cast(dict[str, object], payload))
    values["state"] = state
    return JobEnvelope.model_validate_json(json.dumps(values, separators=(",", ":")))


def _claim_from_row(row: Any) -> JobClaim:
    owner = row["lease_owner"]
    token = row["lease_token"]
    leased_at = row["leased_at"]
    expires_at = row["lease_expires_at"]
    if owner is None or token is None or leased_at is None or expires_at is None:
        raise ValueError("persisted lease is incomplete")
    return JobClaim(
        job=_job_from_row(row["payload"], row["state"]),
        owner=owner,
        token=token,
        attempt_number=int(row["attempt_count"]),
        leased_at=leased_at,
        expires_at=expires_at,
    )
