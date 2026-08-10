"""Transactional persistence boundary for one orchestration action."""

from __future__ import annotations

import json
from types import TracebackType
from typing import Any, Self, cast
from uuid import UUID

from sqlalchemy import Table, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, AsyncSessionTransaction

from money_machine.domain.enums import ProductState
from money_machine.domain.events import DomainEvent
from money_machine.domain.models.candidate import CandidateShortlist
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.listing import ListingPackage
from money_machine.domain.models.product import BuildResult
from money_machine.domain.models.workflow import (
    WorkflowBlocker,
    WorkflowRun,
    workflow_blocker_payload,
)
from money_machine.domain.value_objects import FrozenModel, canonical_json, canonical_sha256
from money_machine.domain.workflow_progress import (
    next_product_state,
    terminal_event_name,
    terminal_product_state,
    validate_terminal_result,
)
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
        result_identity = str(self._result_identity(result_type, result_payload))
        result_sha256 = canonical_sha256(result_payload)
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
                    result_type=result_type,
                    result_id=result_identity,
                    result_sha256=result_sha256,
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
        await self._insert_result(
            result_type,
            result_payload,
            workflow_run_id=workflow_run_id,
        )
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
        if event.occurred_at < workflow.updated_at:
            raise ValueError("workflow event time precedes current update")
        target = next_product_state(job_type, workflow.state, event.name)
        advanced = WorkflowRun(
            schema_version=workflow.schema_version,
            workflow_run_id=workflow.workflow_run_id,
            workflow_type=workflow.workflow_type,
            packet_id=workflow.packet_id,
            state=target,
            idempotency_key=workflow.idempotency_key,
            created_at=workflow.created_at,
            updated_at=event.occurred_at,
        )
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

    async def commit_job_terminal(
        self,
        job_id: UUID,
        lease_token: str,
        attempt_number: int,
        blocker: WorkflowBlocker,
        event: DomainEvent,
        *,
        result_type: str | None = None,
        result_payload: FrozenModel | None = None,
    ) -> None:
        """Atomically persist an adverse terminal result, blocker, event, job and workflow."""

        if (result_type is None) is not (result_payload is None):
            raise ValueError("terminal result type and payload must be provided together")
        if blocker.terminal_state is not ProductState.FAILED and result_payload is None:
            raise ValueError("business terminal requires a durable step result")
        if blocker.job_id != job_id or event.job_id != job_id:
            raise ValueError("job terminal blocker binding mismatch")
        if event.name is not terminal_event_name(blocker.terminal_state):
            raise ValueError("job terminal event name mismatch")
        if event.occurred_at != blocker.occurred_at:
            raise ValueError("job terminal event time mismatch")
        expected_event_payload = workflow_blocker_payload(blocker)
        expected_event_hash = canonical_sha256(expected_event_payload)
        if (
            canonical_sha256(event.payload) != expected_event_hash
            or event.payload_sha256 != expected_event_hash
        ):
            raise ValueError("job terminal event payload mismatch")
        result_identity: str | None = None
        result_sha256: str | None = None
        if result_type is not None and result_payload is not None:
            result_identity = str(self._result_identity(result_type, result_payload))
            result_sha256 = canonical_sha256(result_payload)
            if (
                blocker.result_type != result_type
                or blocker.result_id != result_identity
                or blocker.result_sha256 != result_sha256
            ):
                raise ValueError("job terminal result identity mismatch")
        elif any(
            value is not None
            for value in (blocker.result_type, blocker.result_id, blocker.result_sha256)
        ):
            raise ValueError("job terminal blocker declares an absent result")

        session = self._require_session()
        job_target = "FAILED" if blocker.terminal_state is ProductState.FAILED else "SUCCEEDED"
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
                    state=job_target,
                    lease_owner=None,
                    lease_token=None,
                    leased_at=None,
                    lease_expires_at=None,
                    result_type=result_type,
                    result_id=result_identity,
                    result_sha256=result_sha256,
                    updated_at=event.occurred_at,
                )
                .returning(jobs.c.workflow_run_id, jobs.c.job_type)
            ),
        )
        completed_job = completion.one_or_none()
        if completed_job is None:
            raise ValueError("job terminal lease mismatch")
        workflow_run_id, job_type = completed_job
        if event.workflow_run_id != workflow_run_id:
            raise ValueError("job terminal event binding mismatch")
        validate_terminal_result(
            job_type,
            blocker.terminal_state,
            result_type,
            result_payload,
        )

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
                .values(
                    state=job_target,
                    completed_at=event.occurred_at,
                    error_code=(
                        blocker.code if blocker.terminal_state is ProductState.FAILED else None
                    ),
                )
            ),
        )
        if attempt_completion.rowcount != 1:
            raise ValueError("job terminal attempt lease mismatch")
        if result_type is not None and result_payload is not None:
            await self._insert_result(
                result_type,
                result_payload,
                workflow_run_id=workflow_run_id,
            )
        await self.events.add(event)
        await self._terminalize_workflow(
            workflow_run_id,
            job_type,
            blocker,
            event,
        )

    async def _terminalize_workflow(
        self,
        workflow_run_id: UUID,
        job_type: str,
        blocker: WorkflowBlocker,
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
            raise ValueError("workflow missing during job terminalization")
        workflow = WorkflowRun.model_validate_json(json.dumps(row.payload, separators=(",", ":")))
        if event.occurred_at < workflow.updated_at:
            raise ValueError("workflow event time precedes current update")
        target = terminal_product_state(job_type, workflow.state, blocker.terminal_state)
        terminal = WorkflowRun(
            schema_version=workflow.schema_version,
            workflow_run_id=workflow.workflow_run_id,
            workflow_type=workflow.workflow_type,
            packet_id=workflow.packet_id,
            state=target,
            idempotency_key=workflow.idempotency_key,
            created_at=workflow.created_at,
            updated_at=event.occurred_at,
            terminal_blocker=blocker,
        )
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
                    payload=json.loads(canonical_json(terminal)),
                    payload_sha256=canonical_sha256(terminal),
                    updated_at=event.occurred_at,
                )
            ),
        )
        if progress.rowcount != 1:
            raise ValueError("workflow terminal state mismatch")

    async def _insert_result(
        self,
        result_type: str,
        result: FrozenModel,
        *,
        workflow_run_id: UUID,
    ) -> None:
        session = self._require_session()
        table, identity_column, _ = _RESULT_TABLES.get(result_type, (None, None, None))
        identity = self._result_identity(result_type, result)
        if table is None or identity_column is None:
            raise ValueError(f"unsupported result type: {result_type}")
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
        inserted = (
            await session.execute(
                pg_insert(table)
                .values(**values)
                .on_conflict_do_nothing(index_elements=[table.c[identity_column]])
                .returning(table.c[identity_column])
            )
        ).scalar_one_or_none()
        if inserted is None:
            stored_hash = await session.scalar(
                select(table.c.payload_sha256).where(table.c[identity_column] == identity)
            )
            if stored_hash != values["payload_sha256"]:
                raise ValueError(f"identity collision for {identity}")
        await self._persist_related_results(result, workflow_run_id)

    async def _persist_related_results(
        self,
        result: FrozenModel,
        workflow_run_id: UUID,
    ) -> None:
        if type(result) is CandidateShortlist:
            for score in result.candidates:
                await self.research.add_score(result.packet_id, score)
            return
        if type(result) is BuildResult:
            for artifact in result.artifacts:
                await self.artifacts.add(artifact, workflow_run_id=workflow_run_id)
            return
        if type(result) is ListingPackage:
            artifacts = (
                *result.listing_images,
                result.delivery_document,
                result.preview_video,
                result.package_manifest,
            )
            for artifact in artifacts:
                if artifact is not None:
                    await self.artifacts.add(artifact, workflow_run_id=workflow_run_id)

    @staticmethod
    def _result_identity(result_type: str, result: FrozenModel) -> object:
        table, identity_column, identity_attribute = _RESULT_TABLES.get(
            result_type, (None, None, None)
        )
        if table is None or identity_column is None or identity_attribute is None:
            raise ValueError(f"unsupported result type: {result_type}")
        return getattr(result, identity_attribute)


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
