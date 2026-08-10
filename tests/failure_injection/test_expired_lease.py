from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text, update

from money_machine.domain.events import DomainEvent, DomainEventName
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.research import ResearchPacket
from money_machine.domain.value_objects import canonical_sha256
from money_machine.orchestration.engine import OrchestrationEngine
from money_machine.orchestration.leases import LeaseManager
from money_machine.orchestration.retry import retry_delay
from money_machine.orchestration.transition_guard import TransitionGuard
from money_machine.orchestration.worker import HandlerOutcome, Worker
from money_machine.persistence.database import Database
from money_machine.persistence.tables import domain_events, job_attempts, jobs, research_packets
from money_machine.persistence.unit_of_work import UnitOfWork

REPO_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2030, 8, 9, 12, 0, tzinfo=UTC)


def _database_url() -> str:
    return os.environ["MONEY_MACHINE_TEST_DATABASE_URL"]


def _migrate() -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", _database_url())
    command.upgrade(config, "head")
    asyncio.run(_reset())


async def _reset() -> None:
    database = Database.from_url(_database_url())
    async with database.session_factory() as session, session.begin():
        await session.execute(
            text("TRUNCATE TABLE workflow_runs, research_packets, product_specs CASCADE")
        )
    await database.dispose()


def test_retry_delay_is_bounded_and_never_policy_is_terminal() -> None:
    assert retry_delay("TRANSIENT_INTERNAL", 1) == timedelta(seconds=5)
    assert retry_delay("TRANSIENT_INTERNAL", 8) == timedelta(minutes=5)
    assert retry_delay("NEVER", 1) is None
    assert retry_delay("OPERATOR_REQUIRED", 1) is None


def test_expired_lease_recovers_only_when_retry_policy_allows() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        manager = LeaseManager(database, lease_ttl=timedelta(seconds=30))
        await OrchestrationEngine(database).start_first_product("packet-expiry-retry")
        retrying = await manager.claim_next("worker-a", NOW)
        assert retrying is not None
        await manager.mark_running(retrying, NOW)
        async with UnitOfWork(database) as uow:
            assert uow.session is not None
            with pytest.raises(ValueError, match="expiry"):
                await TransitionGuard().require_live_running_lease(
                    uow.session,
                    retrying,
                    retrying.expires_at,
                )
        recovered = await manager.recover_expired(NOW + timedelta(seconds=31))
        assert recovered == 1
        async with database.session_factory() as session:
            row = (
                await session.execute(
                    select(
                        jobs.c.state,
                        jobs.c.available_at,
                        jobs.c.lease_token,
                        jobs.c.lease_owner,
                    ).where(jobs.c.job_id == retrying.job_id)
                )
            ).one()
            attempt = (
                await session.execute(
                    select(
                        job_attempts.c.state, job_attempts.c.completed_at, job_attempts.c.error_code
                    ).where(job_attempts.c.job_id == retrying.job_id)
                )
            ).one()
        assert row == ("RETRY_WAIT", NOW + timedelta(seconds=36), None, None)
        assert attempt == ("FAILED", NOW + timedelta(seconds=31), "EXPIRED_LEASE")
        assert await manager.claim_next("worker-too-early", NOW + timedelta(seconds=35)) is None
        retried = await manager.claim_next("worker-retry", NOW + timedelta(seconds=36))
        assert retried is not None
        assert retried.job_id == retrying.job_id
        assert retried.attempt_number == 2

        await OrchestrationEngine(database).start_first_product("packet-expiry-never")
        async with database.session_factory() as session, session.begin():
            terminal_row = (
                await session.execute(
                    select(jobs.c.job_id, jobs.c.payload)
                    .where(jobs.c.state == "READY", jobs.c.job_id != retrying.job_id)
                    .order_by(jobs.c.created_at, jobs.c.job_id)
                    .limit(1)
                )
            ).one_or_none()
            assert terminal_row is not None
            terminal_payload = dict(terminal_row.payload)
            terminal_payload["retry_class"] = "NEVER"
            await session.execute(
                update(jobs)
                .where(jobs.c.state == "READY", jobs.c.job_id != retrying.job_id)
                .where(jobs.c.job_id == terminal_row.job_id)
                .values(retry_class="NEVER", payload=terminal_payload)
            )
            terminal_id = terminal_row.job_id
        terminal = await manager.claim_next("worker-b", NOW)
        assert terminal is not None and terminal.job_id == terminal_id
        assert await manager.recover_expired(NOW + timedelta(seconds=31)) == 1
        async with database.session_factory() as session:
            assert (
                await session.scalar(select(jobs.c.state).where(jobs.c.job_id == terminal.job_id))
                == "FAILED"
            )
        await database.dispose()

    asyncio.run(scenario())


def test_slow_handler_cannot_terminalize_a_db_clock_expired_lease() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        await OrchestrationEngine(database).start_first_product("packet-slow-handler")
        async with database.session_factory() as session:
            stale_now = await session.scalar(select(func.clock_timestamp()))
        assert stale_now is not None
        packet = ResearchPacket.model_construct(
            packet_id="packet-slow-handler",
            observations=(),
            packet_sha256="a" * 64,
        )

        async def slow_handler(job: JobEnvelope) -> HandlerOutcome:
            await asyncio.sleep(0.4)
            payload = {"packet_id": packet.packet_id}
            return HandlerOutcome(
                result_type="research_packets",
                result=packet,
                event=DomainEvent(
                    event_id=job.job_id,
                    workflow_run_id=job.workflow_run_id,
                    job_id=job.job_id,
                    name=DomainEventName.RESEARCH_PACKET_ADMITTED,
                    occurred_at=stale_now,
                    payload=payload,
                    payload_sha256=canonical_sha256(payload),
                ),
                successor_job_type="QUALIFY_CANDIDATES",
            )

        worker = Worker(
            database,
            worker_id="worker-slow-handler",
            handlers={"ADMIT_RESEARCH_PACKET": slow_handler},
            lease_ttl=timedelta(milliseconds=100),
            clock=lambda: stale_now,
        )
        result = await worker.run_once()
        assert result.status == "failed"
        assert result.job_id is not None

        async with database.session_factory() as session:
            expired_job = (
                await session.execute(
                    select(jobs.c.state, jobs.c.lease_owner, jobs.c.lease_token).where(
                        jobs.c.job_id == result.job_id
                    )
                )
            ).one()
            authoritative_now = await session.scalar(select(func.clock_timestamp()))
            assert await session.scalar(select(func.count()).select_from(research_packets)) == 0
            assert await session.scalar(select(func.count()).select_from(domain_events)) == 0
        assert expired_job[0] == "RUNNING"
        assert expired_job[1] == "worker-slow-handler"
        assert expired_job[2] is not None
        assert authoritative_now is not None

        assert (
            await LeaseManager(database, lease_ttl=timedelta(milliseconds=100)).recover_expired(
                authoritative_now
            )
            == 1
        )
        async with database.session_factory() as session:
            assert (
                await session.scalar(select(jobs.c.state).where(jobs.c.job_id == result.job_id))
                == "RETRY_WAIT"
            )
            attempt = (
                await session.execute(
                    select(job_attempts.c.state, job_attempts.c.error_code).where(
                        job_attempts.c.job_id == result.job_id
                    )
                )
            ).one()
            assert attempt == ("FAILED", "EXPIRED_LEASE")
        await database.dispose()

    asyncio.run(scenario())
