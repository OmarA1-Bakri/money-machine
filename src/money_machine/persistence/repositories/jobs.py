"""Durable job access.

Reads are available now. Claiming, leasing and transitioning a job are commissioned in
Session 03: this module deliberately exposes no claim method (corrective addendum 1).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from money_machine.domain.enums import JobStatus
from money_machine.persistence.repositories._base import VersionedRepository
from money_machine.persistence.tables import Job, JobDependency


class JobRepository(VersionedRepository[Job]):
    """Durable jobs, read-only with respect to claiming."""

    model = Job

    async def by_idempotency_key(self, key: str) -> Job | None:
        """Fetch the single job holding one idempotency key."""
        statement = select(Job).where(Job.idempotency_key == key)
        return (await self.session.execute(statement)).scalars().one_or_none()

    async def ready_due(self, now: datetime, *, limit: int = 50) -> tuple[Job, ...]:
        """Jobs that are ready and due, oldest first. Reading is not claiming."""
        statement = (
            select(Job)
            .where(Job.status == JobStatus.READY.value, Job.scheduled_at <= now)
            .order_by(Job.scheduled_at)
            .limit(limit)
        )
        return tuple((await self.session.execute(statement)).scalars().all())

    async def in_workflow(self, workflow_id: UUID) -> tuple[Job, ...]:
        """Every job belonging to one workflow, in creation order."""
        statement = select(Job).where(Job.workflow_id == workflow_id).order_by(Job.created_at)
        return tuple((await self.session.execute(statement)).scalars().all())

    async def unsatisfied_dependencies(self, job_id: UUID) -> tuple[JobDependency, ...]:
        """Dependencies that still block one job."""
        statement = select(JobDependency).where(
            JobDependency.job_id == job_id,
            JobDependency.satisfied_at.is_(None),
        )
        return tuple((await self.session.execute(statement)).scalars().all())
