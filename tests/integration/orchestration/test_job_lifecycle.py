from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, func, select, text

from money_machine.domain.events import DomainEvent, DomainEventName
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.product_spec import ProductFact, ProductSpec
from money_machine.domain.models.research import ResearchPacket
from money_machine.domain.value_objects import canonical_sha256
from money_machine.orchestration.engine import OrchestrationEngine
from money_machine.orchestration.leases import LeaseManager
from money_machine.orchestration.worker import HandlerOutcome, Worker
from money_machine.persistence.database import Database
from money_machine.persistence.repositories.jobs import JobRepository
from money_machine.persistence.tables import (
    domain_events,
    job_attempts,
    jobs,
    product_specs,
    research_packets,
    workflow_runs,
)

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


def _product_spec() -> ProductSpec:
    return ProductSpec(
        product_spec_id="PS-worker",
        candidate_id="candidate-worker",
        identity_niche="students",
        base_category="planner",
        target_buyer="People managing students",
        promised_outcome="A structured planner workspace",
        hubs=("home", "courses", "tasks", "calendar", "notes", "review"),
        colour_variants=("ink", "sage", "sand"),
        features=("weekly review",),
        product_facts=(
            ProductFact(
                claim="Configured with 6 hubs",
                category="HUB_INVENTORY",
                evidence_ids=("EV-1",),
            ),
            ProductFact(claim="Includes weekly review", category="FEATURE", evidence_ids=("EV-1",)),
            ProductFact(
                claim="Configured with 3 colour variants",
                category="COLOUR_VARIANTS",
                evidence_ids=("EV-1",),
            ),
            ProductFact(
                claim="People managing students", category="BUYER_FIT", evidence_ids=("EV-1",)
            ),
            ProductFact(
                claim="A structured planner workspace",
                category="WORKFLOW_OUTCOME",
                evidence_ids=("EV-1",),
            ),
        ),
        source_evidence_ids=("EV-1",),
        spec_sha256="c" * 64,
    )


def test_worker_commits_result_event_and_declared_successor_atomically() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        workflow_id = await OrchestrationEngine(database).start_first_product("packet-worker-001")
        packet = ResearchPacket.model_construct(
            packet_id="packet-worker-001",
            observations=(),
            packet_sha256="a" * 64,
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
                    occurred_at=NOW + timedelta(seconds=1),
                    payload=payload,
                    payload_sha256=canonical_sha256(payload),
                ),
                successor_job_type="SCORE_AND_SHORTLIST",
            )

        worker = Worker(
            database,
            worker_id="worker-success",
            handlers={"ADMIT_RESEARCH_PACKET": handler},
            lease_ttl=timedelta(seconds=30),
            clock=lambda: NOW,
        )
        result = await worker.run_once()
        assert result.status == "processed"

        async with database.session_factory() as session:
            states = (
                await session.execute(
                    select(jobs.c.job_type, jobs.c.state)
                    .where(jobs.c.workflow_run_id == workflow_id)
                    .order_by(jobs.c.created_at, jobs.c.job_id)
                )
            ).all()
            assert states[:3] == [
                ("ADMIT_RESEARCH_PACKET", "SUCCEEDED"),
                ("SCORE_AND_SHORTLIST", "READY"),
                ("CREATE_PRODUCT_SPEC", "PENDING"),
            ]
            assert await session.scalar(select(func.count()).select_from(research_packets)) == 1
            assert await session.scalar(select(func.count()).select_from(domain_events)) == 1
        await database.dispose()

    asyncio.run(scenario())


def test_worker_rejects_wrong_result_event_semantics_without_durable_effects() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        workflow_id = await OrchestrationEngine(database).start_first_product(
            "packet-worker-wrong-semantics"
        )
        spec = _product_spec().model_copy(update={"product_spec_id": "PS-worker-wrong"})

        async def wrong_handler(job: JobEnvelope) -> HandlerOutcome:
            payload = {"product_spec_id": spec.product_spec_id}
            return HandlerOutcome(
                result_type="product_specs",
                result=spec,
                event=DomainEvent(
                    event_id=job.job_id,
                    workflow_run_id=job.workflow_run_id,
                    job_id=job.job_id,
                    name=DomainEventName.PRODUCT_SPEC_CREATED,
                    occurred_at=NOW,
                    payload=payload,
                    payload_sha256=canonical_sha256(payload),
                ),
                successor_job_type="SCORE_AND_SHORTLIST",
            )

        worker = Worker(
            database,
            worker_id="worker-wrong-semantics",
            handlers={"ADMIT_RESEARCH_PACKET": wrong_handler},
            lease_ttl=timedelta(seconds=30),
            clock=lambda: NOW,
        )
        result = await worker.run_once()
        assert result.status == "failed"

        async with database.session_factory() as session:
            states = (
                await session.execute(
                    select(jobs.c.job_type, jobs.c.state)
                    .where(jobs.c.workflow_run_id == workflow_id)
                    .order_by(jobs.c.created_at, jobs.c.job_id)
                )
            ).all()
            assert states[:3] == [
                ("ADMIT_RESEARCH_PACKET", "FAILED"),
                ("SCORE_AND_SHORTLIST", "PENDING"),
                ("CREATE_PRODUCT_SPEC", "PENDING"),
            ]
            assert await session.scalar(select(func.count()).select_from(product_specs)) == 0
            assert await session.scalar(select(func.count()).select_from(domain_events)) == 0
        await database.dispose()

    asyncio.run(scenario())


def test_unknown_handler_and_undeclared_successor_fail_closed() -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        async with database.session_factory() as session, session.begin():
            await session.execute(delete(workflow_runs))
            await session.execute(delete(product_specs))
        first_workflow = await OrchestrationEngine(database).start_first_product(
            "packet-worker-unknown"
        )
        unknown = Worker(
            database,
            worker_id="worker-unknown",
            handlers={},
            lease_ttl=timedelta(seconds=30),
            clock=lambda: NOW,
        )
        assert (await unknown.run_once()).status == "failed"

        async with database.session_factory() as session:
            assert (
                await session.scalar(
                    select(jobs.c.state)
                    .where(jobs.c.workflow_run_id == first_workflow)
                    .order_by(jobs.c.created_at, jobs.c.job_id)
                    .limit(1)
                )
                == "FAILED"
            )

        second_workflow = await OrchestrationEngine(database).start_first_product(
            "packet-worker-bad-successor"
        )
        spec = _product_spec().model_copy(update={"product_spec_id": "PS-worker-bad"})

        async def bad_handler(job: JobEnvelope) -> HandlerOutcome:
            payload = {"product_spec_id": spec.product_spec_id}
            return HandlerOutcome(
                result_type="product_specs",
                result=spec,
                event=DomainEvent(
                    event_id=job.job_id,
                    workflow_run_id=job.workflow_run_id,
                    job_id=job.job_id,
                    name=DomainEventName.PRODUCT_SPEC_CREATED,
                    occurred_at=NOW,
                    payload=payload,
                    payload_sha256=canonical_sha256(payload),
                ),
                successor_job_type="RUN_PRODUCT_QA",
            )

        bad = Worker(
            database,
            worker_id="worker-bad-successor",
            handlers={"ADMIT_RESEARCH_PACKET": bad_handler},
            lease_ttl=timedelta(seconds=30),
            clock=lambda: NOW,
        )
        failure = await bad.run_once()
        assert failure.status == "failed"
        async with database.session_factory() as session:
            assert (
                await session.scalar(
                    select(jobs.c.state)
                    .where(jobs.c.workflow_run_id == second_workflow)
                    .order_by(jobs.c.created_at, jobs.c.job_id)
                    .limit(1)
                )
                == "FAILED"
            )
            assert await session.scalar(select(func.count()).select_from(product_specs)) == 0
            assert await session.scalar(select(func.count()).select_from(domain_events)) == 0
        await database.dispose()

    asyncio.run(scenario())


def test_unknown_handler_after_lease_expiry_returns_structured_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        workflow_id = await OrchestrationEngine(database).start_first_product(
            "packet-worker-expired-unknown"
        )
        async with database.session_factory() as session:
            stale_now = await session.scalar(select(func.clock_timestamp()))
        assert stale_now is not None

        original_get = JobRepository.get

        async def delayed_get(self: JobRepository, job_id: UUID) -> JobEnvelope | None:
            await asyncio.sleep(0.4)
            return await original_get(self, job_id)

        monkeypatch.setattr(JobRepository, "get", delayed_get)
        worker = Worker(
            database,
            worker_id="worker-expired-unknown",
            handlers={},
            lease_ttl=timedelta(milliseconds=100),
            clock=lambda: stale_now,
        )
        result = await worker.run_once()
        assert result.status == "failed"
        assert result.error_code == "UNKNOWN_HANDLER"
        assert result.job_id is not None

        async with database.session_factory() as session:
            leased = (
                await session.execute(
                    select(jobs.c.state, jobs.c.lease_owner, jobs.c.lease_token).where(
                        jobs.c.job_id == result.job_id
                    )
                )
            ).one()
            authoritative_now = await session.scalar(select(func.clock_timestamp()))
        assert leased[0] == "LEASED"
        assert leased[1] == "worker-expired-unknown"
        assert leased[2] is not None
        assert authoritative_now is not None

        monkeypatch.setattr(JobRepository, "get", original_get)
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
            assert (
                await session.scalar(
                    select(jobs.c.workflow_run_id).where(jobs.c.job_id == result.job_id)
                )
                == workflow_id
            )
        await database.dispose()

    asyncio.run(scenario())
