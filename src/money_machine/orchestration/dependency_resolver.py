"""Activation of declared successors through the durable job repository."""

from uuid import UUID

from money_machine.persistence.repositories.jobs import JobRepository


class DependencyResolver:
    async def activate_successor(
        self,
        jobs: JobRepository,
        parent_job_id: UUID,
        successor_job_type: str,
    ) -> UUID:
        return await jobs.activate_successor(parent_job_id, successor_job_type)
