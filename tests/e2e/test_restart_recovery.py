from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text

from money_machine.domain.events import DomainEvent, DomainEventName
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.research import ResearchPacket
from money_machine.domain.value_objects import canonical_sha256
from money_machine.orchestration.engine import OrchestrationEngine
from money_machine.orchestration.leases import LeaseManager
from money_machine.orchestration.worker import HandlerOutcome, Worker
from money_machine.persistence.database import Database
from money_machine.persistence.tables import domain_events, job_attempts, jobs, research_packets

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


def test_process_restart_reclaims_once_and_commits_without_duplicate_outputs() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        workflow_id = await OrchestrationEngine(database).start_first_product("packet-restart")
        crashed = await LeaseManager(database, lease_ttl=timedelta(seconds=30)).claim_next(
            "worker-crashed", NOW
        )
        assert crashed is not None

        restarted = LeaseManager(database, lease_ttl=timedelta(seconds=30))
        assert await restarted.recover_expired(NOW + timedelta(seconds=31)) == 1
        resumed_at = NOW + timedelta(seconds=36)
        packet = ResearchPacket.model_construct(
            packet_id="packet-restart",
            observations=(),
            packet_sha256="d" * 64,
        )

        async def handler(job: JobEnvelope) -> HandlerOutcome:
            payload = {"packet_id": packet.packet_id}
            return HandlerOutcome(
                result_type="research_packets",
                result=packet,
                event=DomainEvent(
                    event_id=job.job_id,
                    workflow_run_id=job.workflow_run_id,
                    job_id=job.job_id,
                    name=DomainEventName.RESEARCH_PACKET_ADMITTED,
                    occurred_at=resumed_at,
                    payload=payload,
                    payload_sha256=canonical_sha256(payload),
                ),
                successor_job_type="QUALIFY_CANDIDATES",
            )

        worker = Worker(
            database,
            worker_id="worker-restarted",
            handlers={"ADMIT_RESEARCH_PACKET": handler},
            lease_ttl=timedelta(seconds=30),
            clock=lambda: resumed_at,
        )
        assert (await worker.run_once()).status == "processed"
        async with database.session_factory() as session:
            first_job_id = await session.scalar(
                select(jobs.c.job_id)
                .where(jobs.c.workflow_run_id == workflow_id)
                .order_by(jobs.c.created_at, jobs.c.job_id)
                .limit(1)
            )
            assert first_job_id == crashed.job_id
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(job_attempts)
                    .where(job_attempts.c.job_id == first_job_id)
                )
                == 2
            )
            assert await session.scalar(select(func.count()).select_from(research_packets)) == 1
            assert await session.scalar(select(func.count()).select_from(domain_events)) == 1
        await database.dispose()

    asyncio.run(scenario())
