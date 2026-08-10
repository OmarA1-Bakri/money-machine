from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import select, text

from money_machine.orchestration.engine import OrchestrationEngine
from money_machine.orchestration.scheduler import Scheduler, ScheduleRecord
from money_machine.orchestration.workflows.product_experiment import (
    FIRST_PRODUCT_JOB_SEQUENCE,
    FIRST_PRODUCT_STEP_OUTPUTS,
)
from money_machine.persistence.database import Database
from money_machine.persistence.tables import job_dependencies, jobs, workflow_runs

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_first_product_step_output_contract_is_exact_for_all_eight_jobs() -> None:
    actual = tuple(
        (
            job_type,
            contract.result_type,
            contract.result_model.__name__,
            contract.event_name.value,
            contract.successor_job_type,
        )
        for job_type, contract in FIRST_PRODUCT_STEP_OUTPUTS.items()
    )
    assert actual == (
        (
            "ADMIT_RESEARCH_PACKET",
            "research_packets",
            "ResearchPacket",
            "research_packet_admitted",
            "QUALIFY_CANDIDATES",
        ),
        (
            "QUALIFY_CANDIDATES",
            "candidate_shortlists",
            "CandidateShortlist",
            "candidate_shortlisted",
            "CREATE_PRODUCT_SPEC",
        ),
        (
            "CREATE_PRODUCT_SPEC",
            "product_specs",
            "ProductSpec",
            "product_spec_created",
            "CHECK_CATALOGUE_DEDUPE",
        ),
        (
            "CHECK_CATALOGUE_DEDUPE",
            "dedupe_results",
            "DedupeResult",
            "dedupe_passed",
            "BUILD_PRODUCT",
        ),
        (
            "BUILD_PRODUCT",
            "build_results",
            "BuildResult",
            "product_built",
            "RUN_PRODUCT_QA",
        ),
        (
            "RUN_PRODUCT_QA",
            "product_qa_results",
            "ProductQAResult",
            "product_qa_passed",
            "CREATE_LISTING_PACKAGE",
        ),
        (
            "CREATE_LISTING_PACKAGE",
            "listing_packages",
            "ListingPackage",
            "listing_package_created",
            "RUN_PREFLIGHT",
        ),
        (
            "RUN_PREFLIGHT",
            "preflight_results",
            "PreflightResult",
            "draft_ready",
            None,
        ),
    )


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


def test_first_product_template_is_complete_ordered_and_replay_stable() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        engine = OrchestrationEngine(database)
        first_id = await engine.start_first_product("packet-template-001")
        replay_id = await engine.start_first_product("packet-template-001")
        assert replay_id == first_id

        async with database.session_factory() as session:
            workflow_rows = (await session.execute(select(workflow_runs))).mappings().all()
            job_rows = (
                (
                    await session.execute(
                        select(jobs.c.job_id, jobs.c.job_type, jobs.c.state, jobs.c.idempotency_key)
                        .where(jobs.c.workflow_run_id == first_id)
                        .order_by(jobs.c.created_at, jobs.c.job_id)
                    )
                )
                .mappings()
                .all()
            )
            dependency_rows = (
                await session.execute(
                    select(job_dependencies.c.job_id, job_dependencies.c.depends_on_job_id)
                )
            ).all()

        assert len(workflow_rows) == 1
        assert tuple(row["job_type"] for row in job_rows) == FIRST_PRODUCT_JOB_SEQUENCE
        assert job_rows[0]["state"] == "READY"
        assert all(row["state"] == "PENDING" for row in job_rows[1:])
        assert len(dependency_rows) == len(FIRST_PRODUCT_JOB_SEQUENCE) - 1
        predecessor_by_job = {job_id: predecessor_id for job_id, predecessor_id in dependency_rows}
        for previous, current in pairwise(job_rows):
            assert predecessor_by_job[current["job_id"]] == previous["job_id"]
        assert len({row["idempotency_key"] for row in job_rows}) == len(job_rows)
        await database.dispose()

    asyncio.run(scenario())


def test_scheduler_requires_an_explicit_due_record_and_is_replay_idle() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        now = datetime(2030, 8, 9, 12, 0, tzinfo=UTC)
        assert await Scheduler(database, schedule=None).enqueue_due(now) == 0
        future = ScheduleRecord(packet_id="packet-future", due_at=now + timedelta(seconds=1))
        assert await Scheduler(database, schedule=future).enqueue_due(now) == 0
        due = ScheduleRecord(packet_id="packet-due", due_at=now)
        scheduler = Scheduler(database, schedule=due)
        assert await scheduler.enqueue_due(now) == 1
        assert await Scheduler(database, schedule=due).enqueue_due(now) == 0
        await database.dispose()

    asyncio.run(scenario())


def test_concurrent_identical_starts_resolve_to_one_workflow() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        engine = OrchestrationEngine(database)
        workflow_ids = await asyncio.gather(
            engine.start_first_product("packet-concurrent"),
            engine.start_first_product("packet-concurrent"),
        )
        assert workflow_ids[0] == workflow_ids[1]
        async with database.session_factory() as session:
            assert len((await session.execute(select(workflow_runs))).all()) == 1
            assert len((await session.execute(select(jobs))).all()) == len(
                FIRST_PRODUCT_JOB_SEQUENCE
            )
        await database.dispose()

    asyncio.run(scenario())
