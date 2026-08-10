from __future__ import annotations

import asyncio
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import delete, insert, select, text, update

from money_machine.agents.registry import FirstProductResultStore
from money_machine.agents.runtime import FirstProductRuntime
from money_machine.application.services.research_service import ResearchService
from money_machine.config.loader import load_first_product_config
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.models.research import ResearchPacket
from money_machine.domain.services.low_ticket import QualificationService
from money_machine.domain.services.product_rules import ProductRules, ProductStrategyService
from money_machine.domain.value_objects import canonical_sha256
from money_machine.persistence.database import Database
from money_machine.persistence.tables import domain_events, jobs
from money_machine.persistence.unit_of_work import UnitOfWork

REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE = REPO_ROOT / "tests/fixtures/research/valid_packet_30.json"
NOW = datetime(2030, 8, 10, 12, tzinfo=UTC)


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


def _alternative_packet(tmp_path: Path) -> ResearchPacket:
    raw = cast(dict[str, object], json.loads(FIXTURE.read_text(encoding="utf-8")))
    observations = cast(list[dict[str, object]], raw["observations"])
    for index, observation in enumerate(observations, start=1):
        observation["observation_id"] = f"ALT-OBS-{index:03d}"
        observation["title"] = f"Alternative {observation['title']}"
        evidence = cast(dict[str, object], observation["evidence"])
        evidence["evidence_id"] = f"ALT-EVD-{index:03d}"
        evidence["content_sha256"] = f"{index + 1000:064x}"
    path = tmp_path / "alternative-packet.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return ResearchService().import_packet(path, now=NOW)


async def _completed_admission(
    tmp_path: Path,
) -> tuple[Database, FirstProductResultStore, UUID, UUID, ResearchPacket]:
    database = Database.from_url(_database_url())
    packet = ResearchService().import_packet(FIXTURE, now=NOW)
    alternative = _alternative_packet(tmp_path)
    async with UnitOfWork(database) as uow:
        await uow.research.add_packet(packet)
        await uow.research.add_packet(alternative)

    runtime = FirstProductRuntime(
        database,
        artifact_root=tmp_path / "artifacts",
        config_root=REPO_ROOT / "config",
        worker_id="result-store-worker",
        clock=lambda: NOW,
    )
    workflow_run_id = await runtime.start(packet.packet_id)
    processed = await runtime.run_once()
    assert processed.status == "processed"

    async with database.session_factory() as session:
        job_id = cast(
            UUID,
            await session.scalar(
                select(jobs.c.job_id).where(
                    jobs.c.workflow_run_id == workflow_run_id,
                    jobs.c.job_type == "ADMIT_RESEARCH_PACKET",
                )
            ),
        )
    return (
        database,
        FirstProductResultStore(database),
        workflow_run_id,
        job_id,
        alternative,
    )


EventMutation = Callable[[dict[str, object], UUID, UUID, ResearchPacket], None]


def _wrong_workflow(
    payload: dict[str, object], _workflow_id: UUID, _job_id: UUID, _alternative: ResearchPacket
) -> None:
    payload["workflow_run_id"] = str(uuid4())


def _wrong_job(
    payload: dict[str, object], _workflow_id: UUID, _job_id: UUID, _alternative: ResearchPacket
) -> None:
    payload["job_id"] = str(uuid4())


def _wrong_embedded_hash(
    payload: dict[str, object], _workflow_id: UUID, _job_id: UUID, _alternative: ResearchPacket
) -> None:
    payload["payload_sha256"] = "0" * 64


def _wrong_identity(
    payload: dict[str, object], _workflow_id: UUID, _job_id: UUID, alternative: ResearchPacket
) -> None:
    event_body = cast(dict[str, object], payload["payload"])
    event_body["packet_id"] = alternative.packet_id
    event_body["result_id"] = alternative.packet_id
    event_body["result_sha256"] = canonical_sha256(alternative)


@pytest.mark.parametrize(
    "mutation, normalized_hash, recompute_hashes",
    [
        (_wrong_workflow, None, False),
        (_wrong_job, None, False),
        (_wrong_embedded_hash, None, False),
        (_wrong_identity, None, True),
        (None, "f" * 64, False),
    ],
    ids=(
        "wrong-workflow",
        "wrong-job",
        "embedded-payload-hash-mismatch",
        "wrong-result-identity",
        "normalized-payload-hash-mismatch",
    ),
)
def test_predecessor_event_envelope_and_identity_are_bound_before_load(
    tmp_path: Path,
    mutation: EventMutation | None,
    normalized_hash: str | None,
    recompute_hashes: bool,
) -> None:
    _migrate()

    async def scenario() -> None:
        database, store, workflow_id, job_id, alternative = await _completed_admission(tmp_path)
        async with database.session_factory() as session, session.begin():
            stored = cast(
                dict[str, object],
                await session.scalar(
                    select(domain_events.c.payload).where(domain_events.c.job_id == job_id)
                ),
            )
            payload = cast(dict[str, object], json.loads(json.dumps(stored)))
            if mutation is not None:
                mutation(payload, workflow_id, job_id, alternative)
            values: dict[str, object] = {"payload": payload}
            if recompute_hashes:
                event_hash = canonical_sha256(cast(dict[str, object], payload["payload"]))
                payload["payload_sha256"] = event_hash
                values["payload_sha256"] = event_hash
            if normalized_hash is not None:
                values["payload_sha256"] = normalized_hash
            await session.execute(
                update(domain_events).where(domain_events.c.job_id == job_id).values(**values)
            )

        with pytest.raises(ValueError):
            await store.load_result(workflow_id, "ADMIT_RESEARCH_PACKET", ResearchPacket)
        await database.dispose()

    asyncio.run(scenario())


@pytest.mark.parametrize("event_count", [0, 2], ids=("missing", "duplicate"))
def test_predecessor_load_requires_exactly_one_durable_event(
    tmp_path: Path, event_count: int
) -> None:
    _migrate()

    async def scenario() -> None:
        database, store, workflow_id, job_id, _alternative = await _completed_admission(tmp_path)
        async with database.session_factory() as session, session.begin():
            row = (
                (
                    await session.execute(
                        select(domain_events).where(domain_events.c.job_id == job_id)
                    )
                )
                .mappings()
                .one()
            )
            await session.execute(delete(domain_events).where(domain_events.c.job_id == job_id))
            if event_count == 2:
                first = dict(row)
                second = dict(first)
                second["event_id"] = uuid4()
                await session.execute(insert(domain_events), [first, second])

        with pytest.raises(LookupError, match="exactly one durable event"):
            await store.load_result(workflow_id, "ADMIT_RESEARCH_PACKET", ResearchPacket)
        await database.dispose()

    asyncio.run(scenario())


def test_product_spec_event_cannot_redirect_to_same_candidate_from_another_packet(
    tmp_path: Path,
) -> None:
    _migrate()

    async def scenario() -> None:
        database, store, workflow_id, _admit_job_id, alternative = await _completed_admission(
            tmp_path
        )
        runtime = FirstProductRuntime(
            database,
            artifact_root=tmp_path / "artifacts",
            config_root=REPO_ROOT / "config",
            worker_id="spec-redirect-worker",
            clock=lambda: NOW,
        )
        assert (await runtime.run_once()).status == "processed"
        assert (await runtime.run_once()).status == "processed"

        qualification = QualificationService()
        alternative_scores = qualification.score(alternative)
        alternative_shortlist = qualification.shortlist(alternative, alternative_scores)
        selected = next(
            score
            for score in alternative_shortlist.candidates
            if score.candidate_id == alternative_shortlist.selected_candidate_id
        )
        config = load_first_product_config(REPO_ROOT / "config")
        alternative_spec = ProductStrategyService().create_spec(
            alternative,
            alternative_shortlist,
            selected,
            ProductRules.from_config(config.product_rules.product),
        )
        async with UnitOfWork(database) as uow:
            await uow.products.add_spec(alternative_spec)

        async with database.session_factory() as session, session.begin():
            job_id = cast(
                UUID,
                await session.scalar(
                    select(jobs.c.job_id).where(
                        jobs.c.workflow_run_id == workflow_id,
                        jobs.c.job_type == "CREATE_PRODUCT_SPEC",
                    )
                ),
            )
            stored = cast(
                dict[str, object],
                await session.scalar(
                    select(domain_events.c.payload).where(domain_events.c.job_id == job_id)
                ),
            )
            envelope = cast(dict[str, object], json.loads(json.dumps(stored)))
            body = cast(dict[str, object], envelope["payload"])
            body["product_spec_id"] = alternative_spec.product_spec_id
            body["result_id"] = alternative_spec.product_spec_id
            body["result_sha256"] = canonical_sha256(alternative_spec)
            event_hash = canonical_sha256(body)
            envelope["payload_sha256"] = event_hash
            await session.execute(
                update(domain_events)
                .where(domain_events.c.job_id == job_id)
                .values(payload=envelope, payload_sha256=event_hash)
            )

        with pytest.raises(ValueError, match="binding"):
            await store.load_result(workflow_id, "CREATE_PRODUCT_SPEC", ProductSpec)
        await database.dispose()

    asyncio.run(scenario())
