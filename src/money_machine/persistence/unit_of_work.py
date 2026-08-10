"""Transactional persistence boundary for one orchestration action."""

from __future__ import annotations

import json
from types import TracebackType
from typing import Any, Self, cast
from uuid import UUID

from sqlalchemy import Table, func, insert, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction

from money_machine.domain.events import DomainEvent
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.workflow import WorkflowRun
from money_machine.domain.value_objects import FrozenModel, canonical_json, canonical_sha256
from money_machine.domain.workflow_progress import next_product_state
from money_machine.persistence.database import Database
from money_machine.persistence.repositories.artifacts import ArtifactRepository
from money_machine.persistence.repositories.events import EventRepository
from money_machine.persistence.repositories.jobs import JobRepository
from money_machine.persistence.repositories.listings import ListingRepository
from money_machine.persistence.repositories.products import ProductRepository
from money_machine.persistence.repositories.research import ResearchRepository
from money_machine.persistence.repositories.workflows import WorkflowRepository
from money_machine.persistence.tables import (
    build_results,
    candidate_shortlists,
    dedupe_results,
    job_attempts,
    jobs,
    listing_packages,
    preflight_results,
    product_qa_results,
    product_specs,
    research_packets,
    workflow_runs,
)


class UnitOfWork:
    """One async session and transaction with typed repositories."""

    def __init__(self, database: Database) -> None:
        self._database = database
        self.session: AsyncSession | None = None
        self._transaction: AsyncSessionTransaction | None = None
        self.jobs: JobRepository
        self.events: EventRepository
        self.artifacts: ArtifactRepository
        self.research: ResearchRepository
        self.products: ProductRepository
        self.listings: ListingRepository
        self.workflows: WorkflowRepository

    async def __aenter__(self) -> Self:
        session = self._database.session_factory()
        self.session = session
        self._transaction = await session.begin()
        self.jobs = JobRepository(session)
        self.events = EventRepository(session)
        self.artifacts = ArtifactRepository(session)
        self.research = ResearchRepository(session)
        self.products = ProductRepository(session)
        self.listings = ListingRepository(session)
        self.workflows = WorkflowRepository(session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._transaction is None or self.session is None:
            return
        try:
            if exc_type is None:
                await self._transaction.commit()
            else:
                await self._transaction.rollback()
        finally:
            await self.session.close()

    def _require_session(self) -> AsyncSession:
        if self.session is None:
            raise RuntimeError("UnitOfWork must be entered before use")
        return self.session

    async def commit_job_success(
        self,
        job_id: UUID,
        lease_token: str,
        attempt_number: int,
        result_type: str,
        result_payload: FrozenModel,
        event: DomainEvent,
        successor: JobEnvelope | None,
    ) -> None:
        """Atomically persist result, attempt, event, parent completion, and successor."""

        session = self._require_session()
        completion = cast(
            CursorResult[Any],
            await session.execute(
                update(jobs)
                .where(
                    jobs.c.job_id == job_id,
                    jobs.c.lease_token == lease_token,
                    jobs.c.attempt_count == attempt_number,
                    jobs.c.state == "RUNNING",
                    jobs.c.lease_expires_at > func.clock_timestamp(),
                )
                .values(
                    state="SUCCEEDED",
                    lease_owner=None,
                    lease_token=None,
                    leased_at=None,
                    lease_expires_at=None,
                    updated_at=event.occurred_at,
                )
                .returning(jobs.c.workflow_run_id, jobs.c.job_type)
            ),
        )
        completed_job = completion.one_or_none()
        if completed_job is None:
            raise ValueError("job completion lease mismatch")
        workflow_run_id, job_type = completed_job
        if event.job_id != job_id or event.workflow_run_id != workflow_run_id:
            raise ValueError("job completion event binding mismatch")

        attempt_completion = cast(
            CursorResult[Any],
            await session.execute(
                update(job_attempts)
                .where(
                    job_attempts.c.job_id == job_id,
                    job_attempts.c.attempt_number == attempt_number,
                    job_attempts.c.lease_token == lease_token,
                    job_attempts.c.state == "RUNNING",
                )
                .values(state="SUCCEEDED", completed_at=event.occurred_at)
            ),
        )
        if attempt_completion.rowcount != 1:
            raise ValueError("job attempt completion lease mismatch")
        await self._insert_result(result_type, result_payload)
        await self.events.add(event)
        await self._advance_workflow(
            workflow_run_id,
            job_type,
            event,
        )
        if successor is not None:
            await self.jobs.add(successor)

    async def _advance_workflow(
        self,
        workflow_run_id: UUID,
        job_type: str,
        event: DomainEvent,
    ) -> None:
        session = self._require_session()
        row = (
            await session.execute(
                select(workflow_runs.c.payload)
                .where(workflow_runs.c.workflow_run_id == workflow_run_id)
                .with_for_update()
            )
        ).one_or_none()
        if row is None:
            raise ValueError("workflow missing during job completion")

        workflow = WorkflowRun.model_validate_json(json.dumps(row.payload, separators=(",", ":")))
        target = next_product_state(job_type, workflow.state, event.name)
        advanced = workflow.model_copy(update={"state": target, "updated_at": event.occurred_at})
        advanced_payload = json.loads(canonical_json(advanced))
        progress = cast(
            CursorResult[Any],
            await session.execute(
                update(workflow_runs)
                .where(
                    workflow_runs.c.workflow_run_id == workflow_run_id,
                    workflow_runs.c.state == workflow.state.value,
                )
                .values(
                    state=target.value,
                    payload=advanced_payload,
                    payload_sha256=canonical_sha256(advanced),
                    updated_at=event.occurred_at,
                )
            ),
        )
        if progress.rowcount != 1:
            raise ValueError("workflow progress state mismatch")

    async def _insert_result(self, result_type: str, result: FrozenModel) -> None:
        session = self._require_session()
        table, identity_column, identity_attribute = _RESULT_TABLES.get(
            result_type, (None, None, None)
        )
        if table is None or identity_column is None or identity_attribute is None:
            raise ValueError(f"unsupported result type: {result_type}")
        identity = getattr(result, identity_attribute)
        values: dict[str, object] = {
            identity_column: identity,
            "payload": json.loads(canonical_json(result)),
            "payload_sha256": canonical_sha256(result),
        }
        for foreign_key in (
            "packet_id",
            "candidate_id",
            "product_spec_id",
            "build_id",
            "listing_package_id",
        ):
            if foreign_key in table.c and hasattr(result, foreign_key):
                values[foreign_key] = getattr(result, foreign_key)
        await session.execute(insert(table).values(**values))


_RESULT_TABLES: dict[str, tuple[Table, str, str]] = {
    "research_packets": (research_packets, "packet_id", "packet_id"),
    "candidate_shortlists": (candidate_shortlists, "shortlist_id", "shortlist_id"),
    "product_specs": (product_specs, "product_spec_id", "product_spec_id"),
    "dedupe_results": (dedupe_results, "dedupe_result_id", "dedupe_result_id"),
    "build_results": (build_results, "build_id", "build_id"),
    "product_qa_results": (product_qa_results, "product_qa_result_id", "qa_result_id"),
    "listing_packages": (listing_packages, "listing_package_id", "listing_package_id"),
    "preflight_results": (preflight_results, "preflight_result_id", "preflight_result_id"),
}
