from __future__ import annotations

import asyncio
import hashlib
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text
from sqlalchemy.sql.schema import Table

from money_machine.agents.runtime import FirstProductRuntime
from money_machine.application.services.research_service import ResearchService
from money_machine.domain.enums import ProductState
from money_machine.orchestration.leases import LeaseManager
from money_machine.persistence.database import Database
from money_machine.persistence.tables import (
    artifacts,
    build_results,
    candidate_shortlists,
    dedupe_results,
    domain_events,
    job_attempts,
    jobs,
    listing_packages,
    preflight_results,
    product_qa_results,
    product_specs,
    qualification_scores,
    research_observations,
    research_packets,
    workflow_runs,
)
from money_machine.persistence.unit_of_work import UnitOfWork

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests/fixtures/research/valid_packet_30.json"
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


def _artifact_snapshot(root: Path) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (
                path.relative_to(root).as_posix(),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            )
            for path in root.rglob("*")
            if path.is_file()
        )
    )


async def _durable_snapshot(
    database: Database,
    workflow_id: UUID,
) -> tuple[tuple[str, tuple[tuple[Any, ...], ...]], ...]:
    tables: tuple[tuple[str, Table, tuple[str, ...]], ...] = (
        (
            "workflow_runs",
            workflow_runs,
            ("workflow_run_id", "state", "payload_sha256"),
        ),
        (
            "jobs",
            jobs,
            (
                "job_id",
                "job_type",
                "state",
                "result_type",
                "result_id",
                "result_sha256",
            ),
        ),
        ("domain_events", domain_events, ("event_id", "name", "payload_sha256")),
        ("artifacts", artifacts, ("artifact_id", "relative_path", "sha256")),
        ("research_packets", research_packets, ("packet_id", "payload_sha256")),
        (
            "research_observations",
            research_observations,
            ("observation_id", "payload_sha256"),
        ),
        (
            "qualification_scores",
            qualification_scores,
            ("qualification_score_id", "payload_sha256"),
        ),
        (
            "candidate_shortlists",
            candidate_shortlists,
            ("shortlist_id", "payload_sha256"),
        ),
        ("product_specs", product_specs, ("product_spec_id", "payload_sha256")),
        ("dedupe_results", dedupe_results, ("dedupe_result_id", "payload_sha256")),
        ("build_results", build_results, ("build_id", "payload_sha256")),
        (
            "product_qa_results",
            product_qa_results,
            ("product_qa_result_id", "payload_sha256"),
        ),
        (
            "listing_packages",
            listing_packages,
            ("listing_package_id", "payload_sha256"),
        ),
        (
            "preflight_results",
            preflight_results,
            ("preflight_result_id", "payload_sha256"),
        ),
    )
    snapshot: list[tuple[str, tuple[tuple[Any, ...], ...]]] = []
    async with database.session_factory() as session:
        for name, table, column_names in tables:
            columns = tuple(table.c[column_name] for column_name in column_names)
            statement = select(*columns).order_by(*columns)
            if "workflow_run_id" in table.c:
                statement = statement.where(table.c.workflow_run_id == workflow_id)
            rows = tuple(tuple(row) for row in (await session.execute(statement)).all())
            snapshot.append((name, rows))
    return tuple(snapshot)


def _restart_equivalence_snapshot(
    snapshot: tuple[tuple[str, tuple[tuple[Any, ...], ...]], ...],
) -> tuple[tuple[str, tuple[tuple[Any, ...], ...]], ...]:
    stable_width = {
        "workflow_runs": 2,
        "jobs": 5,
        "domain_events": 2,
        "artifacts": 3,
    }
    return tuple(
        (
            name,
            tuple(row[: stable_width.get(name, 1)] for row in rows),
        )
        for name, rows in snapshot
    )


def test_process_restart_recovers_expired_lease_to_draft_ready_without_duplicates(
    tmp_path: Path,
) -> None:
    _migrate()

    async def scenario() -> None:
        artifact_root = tmp_path / "artifacts"
        database = Database.from_url(_database_url())
        packet = ResearchService().import_packet(FIXTURE, now=NOW)
        async with UnitOfWork(database) as uow:
            await uow.research.add_packet(packet)

        initial_runtime = FirstProductRuntime(
            database,
            artifact_root=artifact_root,
            config_root=REPO_ROOT / "config",
            worker_id="e2e-crashed-worker",
            clock=lambda: NOW,
            lease_ttl=timedelta(seconds=30),
        )
        workflow_id = await initial_runtime.start(packet.packet_id)
        crashed = await LeaseManager(database, lease_ttl=timedelta(seconds=30)).claim_next(
            "e2e-crashed-worker", NOW
        )
        assert crashed is not None
        await database.dispose()

        recovery_database = Database.from_url(_database_url())
        recovered = await LeaseManager(
            recovery_database,
            lease_ttl=timedelta(seconds=30),
        ).recover_expired(NOW + timedelta(seconds=31))
        assert recovered == 1
        await recovery_database.dispose()

        resumed_at = NOW + timedelta(seconds=36)
        resumed_database = Database.from_url(_database_url())
        resumed_runtime = FirstProductRuntime(
            resumed_database,
            artifact_root=artifact_root,
            config_root=REPO_ROOT / "config",
            worker_id="e2e-restarted-worker",
            clock=lambda: resumed_at,
            lease_ttl=timedelta(seconds=30),
        )
        results = await resumed_runtime.drain(max_jobs=20)
        assert [result.status for result in results] == ["processed"] * 8 + ["idle"]

        async with resumed_database.session_factory() as session:
            workflow_state = await session.scalar(
                select(workflow_runs.c.state).where(workflow_runs.c.workflow_run_id == workflow_id)
            )
            assert workflow_state == ProductState.DRAFT_READY.value
            first_job_id = await session.scalar(
                select(jobs.c.job_id)
                .where(jobs.c.workflow_run_id == workflow_id)
                .order_by(jobs.c.created_at, jobs.c.job_id)
                .limit(1)
            )
            assert first_job_id == crashed.job_id
            attempts = (
                await session.execute(
                    select(job_attempts.c.state, job_attempts.c.error_code)
                    .where(job_attempts.c.job_id == first_job_id)
                    .order_by(job_attempts.c.attempt_number)
                )
            ).all()
            assert attempts == [("FAILED", "EXPIRED_LEASE"), ("SUCCEEDED", None)]
            assert await session.scalar(select(func.count()).select_from(jobs)) == 8
            assert await session.scalar(select(func.count()).select_from(domain_events)) == 8
            assert await session.scalar(select(func.count()).select_from(research_packets)) == 1
            assert await session.scalar(select(func.count()).select_from(product_specs)) == 1
            assert await session.scalar(select(func.count()).select_from(build_results)) == 1
            assert await session.scalar(select(func.count()).select_from(listing_packages)) == 1
            assert await session.scalar(select(func.count()).select_from(preflight_results)) == 1

        durable_before = await _durable_snapshot(resumed_database, workflow_id)
        artifacts_before = _artifact_snapshot(artifact_root)
        await resumed_database.dispose()

        replay_database = Database.from_url(_database_url())
        replay_runtime = FirstProductRuntime(
            replay_database,
            artifact_root=artifact_root,
            config_root=REPO_ROOT / "config",
            worker_id="e2e-replay-worker",
            clock=lambda: resumed_at,
        )
        assert await replay_runtime.start(packet.packet_id) == workflow_id
        assert [result.status for result in await replay_runtime.drain(max_jobs=20)] == ["idle"]
        assert await _durable_snapshot(replay_database, workflow_id) == durable_before
        assert _artifact_snapshot(artifact_root) == artifacts_before
        await replay_database.dispose()

    asyncio.run(scenario())


def test_restart_after_every_completed_stage_matches_uninterrupted_run(
    tmp_path: Path,
) -> None:
    _migrate()

    async def seed_and_start(
        database: Database,
        artifact_root: Path,
        worker_id: str,
    ) -> tuple[FirstProductRuntime, UUID]:
        packet = ResearchService().import_packet(FIXTURE, now=NOW)
        async with UnitOfWork(database) as uow:
            await uow.research.add_packet(packet)
        runtime = FirstProductRuntime(
            database,
            artifact_root=artifact_root,
            config_root=REPO_ROOT / "config",
            worker_id=worker_id,
            clock=lambda: NOW,
        )
        return runtime, await runtime.start(packet.packet_id)

    async def scenario() -> None:
        baseline_root = tmp_path / "baseline"
        baseline_database = Database.from_url(_database_url())
        baseline_runtime, baseline_workflow_id = await seed_and_start(
            baseline_database,
            baseline_root,
            "e2e-baseline-worker",
        )
        assert [result.status for result in await baseline_runtime.drain(max_jobs=20)] == [
            "processed"
        ] * 8 + ["idle"]
        baseline_durable = _restart_equivalence_snapshot(
            await _durable_snapshot(
                baseline_database,
                baseline_workflow_id,
            )
        )
        baseline_artifacts = _artifact_snapshot(baseline_root)
        await baseline_database.dispose()

        for completed_steps in range(1, 8):
            await _reset()
            stage_root = tmp_path / f"stage-{completed_steps}"
            initial_database = Database.from_url(_database_url())
            initial_runtime, workflow_id = await seed_and_start(
                initial_database,
                stage_root,
                f"e2e-stage-{completed_steps}-initial",
            )
            assert workflow_id == baseline_workflow_id
            for _ in range(completed_steps):
                assert (await initial_runtime.run_once()).status == "processed"
            await initial_database.dispose()

            restarted_database = Database.from_url(_database_url())
            restarted_runtime = FirstProductRuntime(
                restarted_database,
                artifact_root=stage_root,
                config_root=REPO_ROOT / "config",
                worker_id=f"e2e-stage-{completed_steps}-restarted",
                clock=lambda: NOW,
            )
            remaining = await restarted_runtime.drain(max_jobs=20)
            assert [result.status for result in remaining] == ["processed"] * (
                8 - completed_steps
            ) + ["idle"]
            assert (
                _restart_equivalence_snapshot(
                    await _durable_snapshot(restarted_database, workflow_id)
                )
                == baseline_durable
            ), f"durable identities changed after stage {completed_steps} restart"
            assert _artifact_snapshot(stage_root) == baseline_artifacts, (
                f"artifact bytes changed after stage {completed_steps} restart"
            )
            await restarted_database.dispose()

    asyncio.run(scenario())
