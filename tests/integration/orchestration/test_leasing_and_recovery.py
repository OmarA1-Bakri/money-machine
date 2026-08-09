from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select, text

from money_machine.orchestration.engine import OrchestrationEngine
from money_machine.orchestration.leases import LeaseManager
from money_machine.persistence.database import Database
from money_machine.persistence.tables import job_attempts, jobs

REPO_ROOT = Path(__file__).resolve().parents[3]
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


def test_concurrent_claim_has_one_winner_and_persists_attempt() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        await OrchestrationEngine(database).start_first_product("packet-lease-001")
        manager = LeaseManager(database, lease_ttl=timedelta(seconds=30))
        claims = await asyncio.gather(
            manager.claim_next("worker-a", NOW),
            manager.claim_next("worker-b", NOW),
        )
        winners = [claim for claim in claims if claim is not None]
        assert len(winners) == 1
        lease = winners[0]
        assert lease.owner in {"worker-a", "worker-b"}
        assert lease.leased_at == NOW
        assert lease.expires_at == NOW + timedelta(seconds=30)
        assert lease.attempt_number == 1

        async with database.session_factory() as session:
            job_row = (
                await session.execute(
                    select(
                        jobs.c.state,
                        jobs.c.lease_owner,
                        jobs.c.lease_token,
                        jobs.c.leased_at,
                        jobs.c.lease_expires_at,
                        jobs.c.attempt_count,
                    ).where(jobs.c.job_id == lease.job_id)
                )
            ).one()
            attempt_row = (
                await session.execute(
                    select(
                        job_attempts.c.state,
                        job_attempts.c.lease_token,
                        job_attempts.c.started_at,
                    ).where(job_attempts.c.job_id == lease.job_id)
                )
            ).one()
        assert job_row == (
            "LEASED",
            lease.owner,
            lease.token,
            NOW,
            NOW + timedelta(seconds=30),
            1,
        )
        assert attempt_row == ("LEASED", lease.token, NOW)
        with pytest.raises(ValueError, match="binding"):
            await manager.heartbeat(replace(lease, owner="other-worker"), NOW)
        with pytest.raises(ValueError, match="binding"):
            await manager.heartbeat(replace(lease, token="wrong-token"), NOW)
        await database.dispose()

    asyncio.run(scenario())
