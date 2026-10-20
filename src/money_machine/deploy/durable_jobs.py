"""Prove one durable job survives a new database connection.

A READY job is committed on an isolated loopback database. A second
connection claims it with ``claim_ready_job``. A third connection still sees
that row RUNNING, and a later job stays READY. The worker process is not
started. Docker is not called.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from money_machine.deploy.controls import ServiceControlRefusal, confirm_exit_78_held
from money_machine.deploy.database_migrations import (
    DatabaseMigrationRefusal,
    refuse_shared_database,
)
from money_machine.domain.enums import JobStatus
from money_machine.orchestration.leases import claim_ready_job
from money_machine.persistence.tables import Job, Shop, WorkflowRun

_NAME = re.compile(r"^mm_t_[0-9a-f]{20}$")
_NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
_LATER = _NOW + timedelta(days=1)
_LEASE = timedelta(minutes=5)


class DurableJobRefusal(ValueError):
    """A durable-job claim used memory, a process, or a shared database."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class DurableJobs:
    """A committed job claimed from a later connection."""

    succeeded: bool
    persisted: bool
    claimed_status: str
    lease_owner: str
    future_status: str
    second_claim: bool
    worker_running: bool
    containers_started: bool


def record_durable_jobs(
    url: str,
    *,
    root: Path | None = None,
    docker_socket: bool = False,
    memory_only: bool = False,
) -> DurableJobs:
    """Commit one due job and claim it from a new connection."""
    if docker_socket:
        raise DurableJobRefusal("docker_socket")
    if memory_only:
        raise DurableJobRefusal("memory")
    _refuse_target(url)
    repo = Path(__file__).resolve().parents[3] if root is None else root
    _require_hold(repo)
    try:
        return asyncio.run(_activate(url))
    except DurableJobRefusal:
        raise
    except Exception as error:
        raise DurableJobRefusal("schema") from error


def _refuse_target(url: str) -> None:
    try:
        refuse_shared_database(url)
    except DatabaseMigrationRefusal as error:
        raise DurableJobRefusal(error.code) from error
    name = make_url(url).database
    if name is None or _NAME.fullmatch(name) is None:
        raise DurableJobRefusal("isolated")


def _require_hold(root: Path) -> None:
    try:
        held = confirm_exit_78_held(root)
    except ServiceControlRefusal as error:
        raise DurableJobRefusal(error.code) from error
    except OSError as error:
        raise DurableJobRefusal("exit_78") from error
    if not held.worker_held or not held.scheduler_held or held.running:
        raise DurableJobRefusal("exit_78")


async def _activate(url: str) -> DurableJobs:
    due_id, future_id = await _insert(url)
    status, owner = await _claim(url, due_id)
    future_status, second = await _reread(url, due_id, future_id, owner)
    return DurableJobs(
        succeeded=True,
        persisted=True,
        claimed_status=status,
        lease_owner=owner,
        future_status=future_status,
        second_claim=second,
        worker_running=False,
        containers_started=False,
    )


async def _insert(url: str) -> tuple[UUID, UUID]:
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    due_id = uuid4()
    future_id = uuid4()
    try:
        async with factory() as session, session.begin():
            shop = Shop(
                id=uuid4(),
                name=f"durable-{uuid4().hex[:12]}",
                connection_state="UNCONNECTED",
                timezone="UTC",
                active=True,
            )
            session.add(shop)
            await session.flush()
            workflow = WorkflowRun(
                id=uuid4(),
                shop_id=shop.id,
                workflow_type="ProductLifecycleWorkflow",
                workflow_version=1,
                product_state="DISCOVERED",
                started_at=_NOW,
                version=1,
            )
            session.add(workflow)
            await session.flush()
            session.add(_ready_job(workflow, due_id, scheduled_at=_NOW, key="durable-due"))
            session.add(_ready_job(workflow, future_id, scheduled_at=_LATER, key="durable-later"))
            await session.flush()
    finally:
        await engine.dispose()
    return due_id, future_id


async def _claim(url: str, due_id: UUID) -> tuple[str, str]:
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session, session.begin():
            claimed = await claim_ready_job(
                session,
                worker_id="worker-0",
                now=_NOW,
                lease_duration=_LEASE,
            )
            if claimed is None or claimed.id != due_id:
                raise DurableJobRefusal("claim")
            if claimed.status != JobStatus.RUNNING.value or claimed.lease_owner != "worker-0":
                raise DurableJobRefusal("claim")
            return claimed.status, "worker-0"
    finally:
        await engine.dispose()


async def _reread(url: str, due_id: UUID, future_id: UUID, owner: str) -> tuple[str, bool]:
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session, session.begin():
            due = await session.get(Job, due_id)
            future = await session.get(Job, future_id)
            again = await claim_ready_job(
                session,
                worker_id="worker-1",
                now=_NOW,
                lease_duration=_LEASE,
            )
            if due is None or due.status != JobStatus.RUNNING.value or due.lease_owner != owner:
                raise DurableJobRefusal("persisted")
            if future is None or future.status != JobStatus.READY.value:
                raise DurableJobRefusal("future")
            if again is not None:
                raise DurableJobRefusal("duplicate")
            return future.status, False
    finally:
        await engine.dispose()


def _ready_job(workflow: WorkflowRun, job_id: UUID, *, scheduled_at: datetime, key: str) -> Job:
    return Job(
        id=job_id,
        workflow_id=workflow.id,
        job_type="ResearchCollectionJob",
        object_type="workflow_runs",
        object_id=workflow.id,
        owner_agent_id="A03",
        status=JobStatus.READY.value,
        input={},
        success_contract={"output_model": "ResearchReport"},
        scheduled_at=scheduled_at,
        attempt=0,
        max_attempts=3,
        idempotency_key=f"{key}:{job_id}",
        side_effect_class="NONE",
        retry_class="SAFE",
        allowed_mode="simulation",
        version=1,
    )
