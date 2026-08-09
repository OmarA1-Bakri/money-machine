"""Durable orchestration entry point."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from money_machine.domain.enums import JobState, ProductState, RetryClass
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.workflow import WorkflowRun
from money_machine.domain.value_objects import canonical_sha256
from money_machine.orchestration.idempotency import (
    job_idempotency_key,
    job_identity,
    workflow_idempotency_key,
    workflow_identity,
)
from money_machine.orchestration.workflows.product_experiment import (
    FIRST_PRODUCT_JOB_SEQUENCE,
    FIRST_PRODUCT_WORKFLOW_TYPE,
)
from money_machine.persistence.database import Database
from money_machine.persistence.unit_of_work import UnitOfWork


class OrchestrationEngine:
    """Create idempotent first-product workflow state in one transaction."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def start_first_product(self, packet_id: str) -> UUID:
        normalized_packet_id = packet_id.strip()
        if not normalized_packet_id:
            raise ValueError("packet_id must not be empty")

        workflow_id = workflow_identity(normalized_packet_id)
        async with UnitOfWork(self._database) as uow:
            if uow.session is None:
                raise RuntimeError("unit of work did not open a session")
            lock_key = int.from_bytes(workflow_id.bytes[:8], "big", signed=True)
            await uow.session.execute(select(func.pg_advisory_xact_lock(lock_key)))
            if await uow.workflows.get(workflow_id) is not None:
                return workflow_id

            created_at = datetime.now(UTC)
            workflow = WorkflowRun(
                workflow_run_id=workflow_id,
                workflow_type=FIRST_PRODUCT_WORKFLOW_TYPE,
                packet_id=normalized_packet_id,
                state=ProductState.RESEARCHED,
                idempotency_key=workflow_idempotency_key(normalized_packet_id),
                created_at=created_at,
                updated_at=created_at,
            )
            await uow.workflows.add(workflow)

            previous_job_id: UUID | None = None
            for index, job_type in enumerate(FIRST_PRODUCT_JOB_SEQUENCE):
                job_id = job_identity(workflow_id, index, job_type)
                job = JobEnvelope(
                    job_id=job_id,
                    workflow_run_id=workflow_id,
                    job_type=job_type,
                    state=JobState.READY if index == 0 else JobState.PENDING,
                    idempotency_key=job_idempotency_key(workflow_id, index, job_type),
                    input_sha256=canonical_sha256(
                        {"packet_id": normalized_packet_id, "job_type": job_type}
                    ),
                    retry_class=RetryClass.TRANSIENT_INTERNAL,
                    max_attempts=3,
                )
                job_created_at = created_at + timedelta(microseconds=index)
                await uow.jobs.add(job, available_at=created_at, created_at=job_created_at)
                if previous_job_id is not None:
                    await uow.jobs.add_dependency(job_id, previous_job_id)
                previous_job_id = job_id

        return workflow_id
