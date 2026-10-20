"""Recover one crashed job after a restart without starting a process.

An isolated loopback database holds two RUNNING jobs. The expired lease is
reclaimed through ``reclaim_expired_leases`` and returns to READY. The live
lease stays RUNNING with the same owner. A second reclaim changes nothing.
Docker is not called, and the worker and scheduler stay Exit 78.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from money_machine.deploy.controls import ServiceControlRefusal, confirm_exit_78_held
from money_machine.deploy.database_migrations import (
    DatabaseMigrationRefusal,
    refuse_shared_database,
)
from money_machine.domain.enums import JobStatus
from money_machine.orchestration.leases import reclaim_expired_leases
from money_machine.persistence.tables import Job, Shop, WorkflowRun

_NAME = re.compile(r"^mm_t_[0-9a-f]{20}$")
_NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)
_EXPIRED_AT = _NOW - timedelta(minutes=5)
_LIVE_UNTIL = _NOW + timedelta(minutes=5)


class RestartRecoveryRefusal(ValueError):
    """A restart touched a process or a database that is not isolated."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RestartRecovery:
    """One expired lease returned to READY, and one live lease left in place."""

    succeeded: bool
    recovered_status: str
    recovered_attempt: int
    lease_cleared: bool
    live_status: str
    live_owner: str
    second_reclaim_count: int
    worker_running: bool
    containers_started: bool


def refuse_process_restart(command: str) -> None:
    """A process restart is not performed."""
    if command.strip() == "":
        raise RestartRecoveryRefusal("unknown")
    raise RestartRecoveryRefusal("process_restart")


def record_restart_recovery(
    url: str,
    *,
    root: Path | None = None,
    docker_socket: bool = False,
    restart_command: str | None = None,
) -> RestartRecovery:
    """Reclaim one expired lease. No container and no worker is started."""
    if docker_socket:
        raise RestartRecoveryRefusal("docker_socket")
    if restart_command is not None:
        refuse_process_restart(restart_command)
    _refuse_target(url)
    repo = Path(__file__).resolve().parents[3] if root is None else root
    _require_hold(repo)
    try:
        return asyncio.run(_recover(url))
    except RestartRecoveryRefusal:
        raise
    except Exception as error:
        raise RestartRecoveryRefusal("schema") from error


def _refuse_target(url: str) -> None:
    try:
        refuse_shared_database(url)
    except DatabaseMigrationRefusal as error:
        raise RestartRecoveryRefusal(error.code) from error
    name = make_url(url).database
    if name is None or _NAME.fullmatch(name) is None:
        raise RestartRecoveryRefusal("isolated")


def _require_hold(root: Path) -> None:
    try:
        held = confirm_exit_78_held(root)
    except ServiceControlRefusal as error:
        raise RestartRecoveryRefusal(error.code) from error
    except OSError as error:
        raise RestartRecoveryRefusal("exit_78") from error
    if not held.worker_held or not held.scheduler_held or held.running:
        raise RestartRecoveryRefusal("exit_78")


async def _recover(url: str) -> RestartRecovery:
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session, session.begin():
            return await _once(session)
    finally:
        await engine.dispose()


async def _once(session: AsyncSession) -> RestartRecovery:
    shop = Shop(
        id=uuid4(),
        name=f"restart-{uuid4().hex[:12]}",
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
    expired = _running_job(
        workflow,
        idempotency_key=f"restart-expired:{uuid4()}",
        owner="worker-crashed",
        lease_expires_at=_EXPIRED_AT,
    )
    live = _running_job(
        workflow,
        idempotency_key=f"restart-live:{uuid4()}",
        owner="worker-live",
        lease_expires_at=_LIVE_UNTIL,
    )
    session.add(expired)
    session.add(live)
    await session.flush()

    first = await reclaim_expired_leases(session, now=_NOW, limit=50)
    if len(first) != 1 or first[0].id != expired.id:
        raise RestartRecoveryRefusal("recover")
    second = await reclaim_expired_leases(session, now=_NOW, limit=50)
    recovered = await session.get(Job, expired.id)
    untouched = await session.get(Job, live.id)
    if recovered is None or untouched is None:
        raise RestartRecoveryRefusal("recover")
    if (
        recovered.status != JobStatus.READY.value
        or recovered.attempt != 1
        or recovered.lease_owner is not None
        or recovered.lease_expires_at is not None
    ):
        raise RestartRecoveryRefusal("recover")
    if (
        untouched.status != JobStatus.RUNNING.value
        or untouched.lease_owner != "worker-live"
        or untouched.attempt != 0
    ):
        raise RestartRecoveryRefusal("live_lease")
    if second:
        raise RestartRecoveryRefusal("repeat")
    return RestartRecovery(
        succeeded=True,
        recovered_status=recovered.status,
        recovered_attempt=recovered.attempt,
        lease_cleared=True,
        live_status=untouched.status,
        live_owner="worker-live",
        second_reclaim_count=0,
        worker_running=False,
        containers_started=False,
    )


def _running_job(
    workflow: WorkflowRun,
    *,
    idempotency_key: str,
    owner: str,
    lease_expires_at: datetime,
) -> Job:
    return Job(
        id=uuid4(),
        workflow_id=workflow.id,
        job_type="ResearchCollectionJob",
        object_type="workflow_runs",
        object_id=workflow.id,
        owner_agent_id="A03",
        status=JobStatus.RUNNING.value,
        input={},
        success_contract={"output_model": "ResearchReport"},
        scheduled_at=_NOW,
        attempt=0,
        max_attempts=3,
        idempotency_key=idempotency_key,
        side_effect_class="NONE",
        retry_class="SAFE",
        allowed_mode="simulation",
        lease_owner=owner,
        lease_expires_at=lease_expires_at,
        heartbeat_at=_EXPIRED_AT,
        version=1,
    )
