"""One-job durable worker with fail-closed handler dispatch."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from money_machine.domain.enums import JobState
from money_machine.domain.events import DomainEvent
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.value_objects import FrozenModel
from money_machine.orchestration._foundation import unavailable
from money_machine.orchestration.dependency_resolver import DependencyResolver
from money_machine.orchestration.event_dispatcher import HandlerRegistry
from money_machine.orchestration.leases import JobLease, LeaseLostError, LeaseManager
from money_machine.orchestration.successor_factory import SuccessorFactory
from money_machine.orchestration.transition_guard import TransitionGuard
from money_machine.orchestration.workflows.product_experiment import validate_step_output
from money_machine.persistence.database import Database
from money_machine.persistence.repositories.jobs import JobRepository
from money_machine.persistence.unit_of_work import UnitOfWork

JobHandler = Callable[[JobEnvelope], Awaitable["HandlerOutcome"]]


@dataclass(frozen=True, slots=True)
class HandlerOutcome:
    result_type: str
    result: FrozenModel
    event: DomainEvent
    successor_job_type: str | None


@dataclass(frozen=True, slots=True)
class WorkerResult:
    status: Literal["processed", "idle", "failed"]
    job_id: UUID | None = None
    error_code: str | None = None


class Worker:
    def __init__(
        self,
        database: Database,
        *,
        worker_id: str,
        handlers: dict[str, JobHandler],
        lease_ttl: timedelta,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._database = database
        self._worker_id = worker_id
        self._handlers = HandlerRegistry(handlers)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._leases = LeaseManager(database, lease_ttl=lease_ttl)
        self._successors = SuccessorFactory()
        self._dependencies = DependencyResolver()
        self._transitions = TransitionGuard()

    async def run_once(self) -> WorkerResult:
        now = self._clock()
        lease = await self._leases.claim_next(self._worker_id, now)
        if lease is None:
            return WorkerResult(status="idle")

        async with self._database.session_factory() as session:
            job = await JobRepository(session).get(lease.job_id)
        if job is None:
            await self._fail_if_owned(lease, now, "JOB_PAYLOAD_MISSING", terminal=True)
            return WorkerResult("failed", lease.job_id, "JOB_PAYLOAD_MISSING")

        try:
            handler = self._handlers.resolve(job.job_type)
        except KeyError:
            await self._fail_if_owned(lease, now, "UNKNOWN_HANDLER", terminal=True)
            return WorkerResult("failed", lease.job_id, "UNKNOWN_HANDLER")

        try:
            await self._leases.mark_running(lease, now)
            job = job.model_copy(update={"state": JobState.RUNNING})
            outcome = await handler(job)
            if (
                outcome.event.job_id != lease.job_id
                or outcome.event.workflow_run_id != job.workflow_run_id
            ):
                raise ValueError("handler event binding mismatch")
            validate_step_output(
                job.job_type,
                outcome.result_type,
                outcome.result,
                outcome.event.name,
                outcome.successor_job_type,
            )
            self._successors.validate(job.job_type, outcome.successor_job_type)
            completion_time = self._clock()
            async with UnitOfWork(self._database) as uow:
                if uow.session is None:
                    raise RuntimeError("unit of work did not open a session")
                session = uow.session
                await self._transitions.require_live_running_lease(session, lease, completion_time)
                await uow.commit_job_success(
                    lease.job_id,
                    lease.token,
                    lease.attempt_number,
                    outcome.result_type,
                    outcome.result,
                    outcome.event,
                    None,
                )
                if outcome.successor_job_type is not None:
                    await self._dependencies.activate_successor(
                        uow.jobs,
                        lease.job_id,
                        outcome.successor_job_type,
                    )
            return WorkerResult("processed", lease.job_id)
        except Exception as exc:
            await self._fail_if_owned(
                lease,
                self._clock(),
                type(exc).__name__.upper(),
                terminal=isinstance(exc, ValueError),
            )
            return WorkerResult("failed", lease.job_id, type(exc).__name__.upper())

    async def _fail_if_owned(
        self,
        lease: JobLease,
        now: datetime,
        error_code: str,
        *,
        terminal: bool,
    ) -> None:
        with suppress(LeaseLostError):
            await self._leases.fail(lease, now, error_code, terminal=terminal)


def main() -> int:
    """Refuse to claim worker capability before it is implemented."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    return unavailable("worker")


if __name__ == "__main__":
    raise SystemExit(main())
