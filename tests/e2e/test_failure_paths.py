from __future__ import annotations

import asyncio
import hashlib
import json
import os
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text, update

from money_machine.agents.runtime import FirstProductRuntime
from money_machine.application.services.listing_service import listing_package_sha256
from money_machine.application.services.research_service import ResearchService
from money_machine.domain.events import DomainEvent, DomainEventName
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.listing import ListingPackage
from money_machine.domain.models.product import BuildResult
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.value_objects import canonical_sha256
from money_machine.orchestration.worker import HandlerOutcome, Worker
from money_machine.orchestration.workflows.product_experiment import success_event_payload
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
NOW = datetime(2030, 8, 10, 12, tzinfo=UTC)


def _database_url() -> str:
    return os.environ["MONEY_MACHINE_TEST_DATABASE_URL"]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


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


async def _start(
    database: Database,
    artifact_root: Path,
    packet_path: Path,
    worker_id: str,
) -> tuple[FirstProductRuntime, UUID]:
    packet = ResearchService().import_packet(packet_path, now=NOW)
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


async def _counts(database: Database) -> dict[str, int]:
    tables = {
        "jobs": jobs,
        "attempts": job_attempts,
        "events": domain_events,
        "packets": research_packets,
        "observations": research_observations,
        "scores": qualification_scores,
        "shortlists": candidate_shortlists,
        "specs": product_specs,
        "dedupe": dedupe_results,
        "builds": build_results,
        "qa": product_qa_results,
        "listings": listing_packages,
        "preflight": preflight_results,
        "artifacts": artifacts,
    }
    async with database.session_factory() as session:
        return {
            name: int(await session.scalar(select(func.count()).select_from(table)) or 0)
            for name, table in tables.items()
        }


async def _workflow_state(database: Database, workflow_id: UUID) -> str:
    async with database.session_factory() as session:
        value = await session.scalar(
            select(workflow_runs.c.state).where(workflow_runs.c.workflow_run_id == workflow_id)
        )
    assert value is not None
    return value


def test_low_scores_terminalize_as_insufficient_evidence_before_product_work(
    tmp_path: Path,
) -> None:
    _migrate()
    payload = deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
    for observation in payload["observations"]:
        observation["qualification_inputs"] = {
            "demand": "7",
            "differentiation": "7",
            "build_feasibility": "7",
            "buyer_value": "7",
        }
    packet_path = tmp_path / "low-score-packet.json"
    packet_path.write_text(json.dumps(payload), encoding="utf-8")

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        runtime, workflow_id = await _start(
            database,
            tmp_path / "artifacts",
            packet_path,
            "e2e-low-score-worker",
        )
        assert [result.status for result in await runtime.drain(max_jobs=8)] == [
            "processed",
            "processed",
            "idle",
        ]
        assert await _workflow_state(database, workflow_id) == "INSUFFICIENT_EVIDENCE"
        assert await _counts(database) == {
            "jobs": 8,
            "attempts": 2,
            "events": 2,
            "packets": 1,
            "observations": 30,
            "scores": 5,
            "shortlists": 1,
            "specs": 0,
            "dedupe": 0,
            "builds": 0,
            "qa": 0,
            "listings": 0,
            "preflight": 0,
            "artifacts": 0,
        }
        async with database.session_factory() as session:
            names = tuple(
                await session.scalars(select(domain_events.c.name).order_by(domain_events.c.name))
            )
            shortlist = await session.scalar(select(candidate_shortlists.c.payload))
        assert names == ("insufficient_evidence", "research_packet_admitted")
        assert shortlist is not None
        assert shortlist["selected_candidate_id"] is None
        assert shortlist["backup_candidate_id"] is None
        await database.dispose()

    asyncio.run(scenario())


def test_catalogue_duplicate_terminalizes_before_build(tmp_path: Path) -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        runtime, workflow_id = await _start(
            database,
            tmp_path / "artifacts",
            FIXTURE,
            "e2e-duplicate-worker",
        )
        for _ in range(3):
            assert (await runtime.run_once()).status == "processed"
        async with database.session_factory() as session:
            payload = await session.scalar(select(product_specs.c.payload))
        assert payload is not None
        generated = ProductSpec.model_validate_json(json.dumps(payload))
        existing = generated.model_copy(update={"product_spec_id": "PS-existing-catalogue"})
        async with UnitOfWork(database) as uow:
            await uow.products.add_spec(existing)

        assert (await runtime.run_once()).status == "processed"
        assert (await runtime.run_once()).status == "idle"
        assert await _workflow_state(database, workflow_id) == "REJECTED"
        counts = await _counts(database)
        assert counts == {
            "jobs": 8,
            "attempts": 4,
            "events": 4,
            "packets": 1,
            "observations": 30,
            "scores": 5,
            "shortlists": 1,
            "specs": 2,
            "dedupe": 1,
            "builds": 0,
            "qa": 0,
            "listings": 0,
            "preflight": 0,
            "artifacts": 0,
        }
        async with database.session_factory() as session:
            dedupe = await session.scalar(select(dedupe_results.c.payload))
        assert dedupe is not None
        assert dedupe["passed"] is False
        assert dedupe["matched_product_spec_ids"] == ["PS-existing-catalogue"]
        await database.dispose()

    asyncio.run(scenario())


def test_corrupted_build_terminalizes_failed_qa_before_listing(tmp_path: Path) -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        runtime, workflow_id = await _start(
            database,
            tmp_path / "artifacts",
            FIXTURE,
            "e2e-qa-failure-worker",
        )
        for _ in range(5):
            assert (await runtime.run_once()).status == "processed"
        async with database.session_factory() as session:
            payload = await session.scalar(select(build_results.c.payload))
        assert payload is not None
        build = BuildResult.model_validate_json(json.dumps(payload))
        with (Path(build.root_artifact_path) / "home.html").open("ab") as handle:
            handle.write(b"\ncorruption")

        assert (await runtime.run_once()).status == "processed"
        assert (await runtime.run_once()).status == "idle"
        assert await _workflow_state(database, workflow_id) == "REJECTED"
        counts = await _counts(database)
        assert counts["attempts"] == 6
        assert counts["events"] == 6
        assert counts["qa"] == 1
        assert counts["listings"] == 0
        assert counts["preflight"] == 0
        async with database.session_factory() as session:
            qa = await session.scalar(select(product_qa_results.c.payload))
        assert qa is not None
        assert qa["passed"] is False
        assert any("home.html" in finding for finding in qa["findings"])
        await database.dispose()

    asyncio.run(scenario())


def test_missing_listing_asset_terminalizes_failed_preflight(tmp_path: Path) -> None:
    _migrate()

    async def scenario() -> None:
        artifact_root = tmp_path / "artifacts"
        database = Database.from_url(_database_url())
        runtime, workflow_id = await _start(
            database,
            artifact_root,
            FIXTURE,
            "e2e-preflight-failure-worker",
        )
        for _ in range(7):
            assert (await runtime.run_once()).status == "processed"
        async with database.session_factory() as session:
            listing = await session.scalar(select(listing_packages.c.payload))
        assert listing is not None
        first_image = listing["listing_images"][0]
        (artifact_root / str(workflow_id) / first_image["relative_path"]).unlink()

        assert (await runtime.run_once()).status == "processed"
        assert (await runtime.run_once()).status == "idle"
        assert await _workflow_state(database, workflow_id) == "REJECTED"
        counts = await _counts(database)
        assert counts["attempts"] == 8
        assert counts["events"] == 8
        assert counts["listings"] == 1
        assert counts["preflight"] == 1
        async with database.session_factory() as session:
            preflight = await session.scalar(select(preflight_results.c.payload))
            names = tuple(await session.scalars(select(domain_events.c.name)))
        assert preflight is not None
        assert preflight["passed"] is False
        assert any("MISSING" in finding for finding in preflight["findings"])
        assert "draft_ready" not in names
        await database.dispose()

    asyncio.run(scenario())


def test_wrong_typed_step_result_has_no_durable_success_effect(tmp_path: Path) -> None:
    _migrate()

    async def scenario() -> None:
        database = Database.from_url(_database_url())
        packet = ResearchService().import_packet(FIXTURE, now=NOW)
        async with UnitOfWork(database) as uow:
            await uow.research.add_packet(packet)
        runtime = FirstProductRuntime(
            database,
            artifact_root=tmp_path / "artifacts",
            config_root=REPO_ROOT / "config",
            worker_id="e2e-unused-runtime-worker",
            clock=lambda: NOW,
        )
        workflow_id = await runtime.start(packet.packet_id)

        async def wrong_handler(job: JobEnvelope) -> HandlerOutcome:
            payload = success_event_payload("product_specs", packet)
            return HandlerOutcome(
                result_type="product_specs",
                result=packet,
                event=DomainEvent(
                    event_id=job.job_id,
                    workflow_run_id=job.workflow_run_id,
                    job_id=job.job_id,
                    name=DomainEventName.RESEARCH_PACKET_ADMITTED,
                    occurred_at=NOW,
                    payload=payload,
                    payload_sha256=canonical_sha256(payload),
                ),
                successor_job_type="QUALIFY_CANDIDATES",
            )

        worker = Worker(
            database,
            worker_id="e2e-wrong-type-worker",
            handlers={"ADMIT_RESEARCH_PACKET": wrong_handler},
            lease_ttl=timedelta(minutes=5),
            clock=lambda: NOW,
        )
        result = await worker.run_once()
        assert result.status == "failed"
        assert result.error_code == "VALUEERROR"
        assert await _workflow_state(database, workflow_id) == "RESEARCHED"
        counts = await _counts(database)
        assert counts["attempts"] == 1
        assert counts["events"] == 0
        assert counts["scores"] == 0
        assert counts["shortlists"] == 0
        assert counts["specs"] == 0
        assert counts["artifacts"] == 0
        async with database.session_factory() as session:
            parent = (
                await session.execute(
                    select(
                        jobs.c.state,
                        jobs.c.result_type,
                        jobs.c.result_id,
                        jobs.c.result_sha256,
                    ).where(
                        jobs.c.workflow_run_id == workflow_id,
                        jobs.c.job_type == "ADMIT_RESEARCH_PACKET",
                    )
                )
            ).one()
        assert parent == ("FAILED", None, None, None)
        await database.dispose()

    asyncio.run(scenario())


def test_coherently_resigned_foreign_image_still_fails_preflight(tmp_path: Path) -> None:
    _migrate()

    async def scenario() -> None:
        artifact_root = tmp_path / "artifacts"
        database = Database.from_url(_database_url())
        runtime, workflow_id = await _start(
            database,
            artifact_root,
            FIXTURE,
            "e2e-forged-artifact-worker",
        )
        for _ in range(7):
            assert (await runtime.run_once()).status == "processed"
        async with database.session_factory() as session:
            stored_listing = await session.scalar(select(listing_packages.c.payload))
        assert stored_listing is not None
        listing = ListingPackage.model_validate_json(json.dumps(stored_listing))
        assert listing.package_manifest is not None

        package_root = artifact_root / str(workflow_id)
        target = listing.listing_images[0]
        source = listing.listing_images[1]
        foreign = (package_root / source.relative_path).read_bytes()
        (package_root / target.relative_path).write_bytes(foreign)
        foreign_sha256 = _sha256_bytes(foreign)
        replacement = target.model_copy(
            update={
                "byte_count": len(foreign),
                "content_sha256": foreign_sha256,
            }
        )

        manifest_path = package_root / listing.package_manifest.relative_path
        manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_entry = next(
            entry
            for entry in manifest_payload["artifacts"]
            if entry["path"] == target.relative_path.as_posix()
        )
        manifest_entry["byte_count"] = len(foreign)
        manifest_entry["sha256"] = foreign_sha256
        manifest_bytes = json.dumps(
            manifest_payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        manifest_path.write_bytes(manifest_bytes)
        manifest = listing.package_manifest.model_copy(
            update={
                "byte_count": len(manifest_bytes),
                "content_sha256": _sha256_bytes(manifest_bytes),
            }
        )
        changed = listing.model_copy(
            update={
                "listing_images": (replacement, *listing.listing_images[1:]),
                "package_manifest": manifest,
                "package_sha256": "0" * 64,
            }
        )
        changed = changed.model_copy(update={"package_sha256": listing_package_sha256(changed)})
        changed_payload = changed.model_dump(mode="json")
        changed_result_hash = canonical_sha256(changed)

        async with database.session_factory() as session, session.begin():
            event_row = (
                await session.execute(
                    select(domain_events.c.event_id, domain_events.c.payload).where(
                        domain_events.c.workflow_run_id == workflow_id,
                        domain_events.c.name == "listing_package_created",
                    )
                )
            ).one()
            event_envelope = deepcopy(event_row.payload)
            event_payload = event_envelope["payload"]
            event_payload["result_sha256"] = changed_result_hash
            event_hash = canonical_sha256(event_payload)
            event_envelope["payload_sha256"] = event_hash

            await session.execute(
                update(listing_packages)
                .where(listing_packages.c.listing_package_id == changed.listing_package_id)
                .values(payload=changed_payload, payload_sha256=changed_result_hash)
            )
            await session.execute(
                update(jobs)
                .where(
                    jobs.c.workflow_run_id == workflow_id,
                    jobs.c.job_type == "CREATE_LISTING_PACKAGE",
                )
                .values(result_sha256=changed_result_hash)
            )
            await session.execute(
                update(domain_events)
                .where(domain_events.c.event_id == event_row.event_id)
                .values(payload=event_envelope, payload_sha256=event_hash)
            )
            for reference in (replacement, manifest):
                await session.execute(
                    update(artifacts)
                    .where(
                        artifacts.c.workflow_run_id == workflow_id,
                        artifacts.c.artifact_id == reference.artifact_id,
                    )
                    .values(
                        byte_count=reference.byte_count,
                        sha256=reference.content_sha256,
                        payload=reference.model_dump(mode="json"),
                    )
                )

        assert (await runtime.run_once()).status == "processed"
        assert (await runtime.run_once()).status == "idle"
        assert await _workflow_state(database, workflow_id) == "REJECTED"
        async with database.session_factory() as session:
            preflight = await session.scalar(select(preflight_results.c.payload))
            names = tuple(await session.scalars(select(domain_events.c.name)))
        assert preflight is not None
        assert preflight["passed"] is False
        assert any(
            finding in preflight["findings"]
            for finding in ("IMAGE_RENDER_MISMATCH", "IMAGE_DIGEST_DUPLICATE")
        )
        assert "draft_ready" not in names
        assert (await _counts(database))["artifacts"] == 24
        await database.dispose()

    asyncio.run(scenario())
