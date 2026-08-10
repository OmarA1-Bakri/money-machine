from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text

from money_machine.agents.runtime import FirstProductRuntime
from money_machine.application.services.research_service import ResearchService
from money_machine.domain.enums import ProductState
from money_machine.domain.models.candidate import CandidateShortlist
from money_machine.domain.models.listing import ListingPackage, PreflightResult
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import DedupeResult, ProductSpec
from money_machine.persistence.database import Database
from money_machine.persistence.tables import (
    artifacts,
    build_results,
    candidate_shortlists,
    dedupe_results,
    domain_events,
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


def test_fixture_packet_reaches_durable_draft_ready(tmp_path: Path) -> None:
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
            worker_id="e2e-happy-worker",
            clock=lambda: NOW,
        )
        workflow_id = await runtime.start(packet.packet_id)
        results = await runtime.drain(max_jobs=20)
        assert [result.status for result in results] == ["processed"] * 8 + ["idle"]

        async with database.session_factory() as session:
            workflow_payload = await session.scalar(
                select(workflow_runs.c.payload).where(
                    workflow_runs.c.workflow_run_id == workflow_id
                )
            )
            assert workflow_payload is not None
            assert workflow_payload["state"] == ProductState.DRAFT_READY.value
            assert await session.scalar(select(func.count()).select_from(jobs)) == 8
            assert await session.scalar(select(func.count()).select_from(domain_events)) == 8
            assert await session.scalar(select(func.count()).select_from(research_packets)) == 1
            assert (
                await session.scalar(select(func.count()).select_from(research_observations)) == 30
            )
            assert await session.scalar(select(func.count()).select_from(qualification_scores)) == 5

            shortlist_payload = await session.scalar(select(candidate_shortlists.c.payload))
            spec_payload = await session.scalar(select(product_specs.c.payload))
            dedupe_payload = await session.scalar(select(dedupe_results.c.payload))
            build_payload = await session.scalar(select(build_results.c.payload))
            qa_payload = await session.scalar(select(product_qa_results.c.payload))
            listing_payload = await session.scalar(select(listing_packages.c.payload))
            preflight_payload = await session.scalar(select(preflight_results.c.payload))

            assert shortlist_payload is not None
            assert spec_payload is not None
            assert dedupe_payload is not None
            assert build_payload is not None
            assert qa_payload is not None
            assert listing_payload is not None
            assert preflight_payload is not None

            shortlist = CandidateShortlist.model_validate_json(json.dumps(shortlist_payload))
            spec = ProductSpec.model_validate_json(json.dumps(spec_payload))
            dedupe = DedupeResult.model_validate_json(json.dumps(dedupe_payload))
            build = BuildResult.model_validate_json(json.dumps(build_payload))
            qa = ProductQAResult.model_validate_json(json.dumps(qa_payload))
            listing = ListingPackage.model_validate_json(json.dumps(listing_payload))
            preflight = PreflightResult.model_validate_json(json.dumps(preflight_payload))

            assert len(shortlist.candidates) == 5
            assert shortlist.selected_candidate_id is not None
            assert shortlist.backup_candidate_id is not None
            assert shortlist.selected_candidate_id != shortlist.backup_candidate_id
            primary = next(
                item
                for item in shortlist.candidates
                if item.candidate_id == shortlist.selected_candidate_id
            )
            assert primary.total >= 30
            assert 6 <= len(spec.hubs) <= 8
            assert 3 <= len(spec.colour_variants) <= 4
            assert dedupe.passed
            assert build.product_spec_id == spec.product_spec_id
            assert qa.passed
            assert len(listing.tags) == 13
            assert len(listing.listing_images) == 10
            assert len({image.content_sha256 for image in listing.listing_images}) == 10
            assert listing.delivery_document is not None
            assert listing.package_manifest is not None
            assert listing.preview_video_status == "GENERATED"
            assert listing.preview_video is not None
            assert listing.preview_video.media_type == "video/mp4"
            assert preflight.passed
            assert preflight.external_effect_mode == "simulation"
            assert preflight.incremental_spend == Decimal("0.00")
            assert await session.scalar(select(func.count()).select_from(artifacts)) == (
                len(build.artifacts)
                + len(listing.listing_images)
                + 2
                + (1 if listing.preview_video is not None else 0)
            )

        assert (tmp_path / "artifacts" / str(workflow_id) / "product").is_dir()
        assert (
            tmp_path
            / "artifacts"
            / str(workflow_id)
            / "listing"
            / listing.listing_package_id
            / "manifest.json"
        ).is_file()
        await database.dispose()

    asyncio.run(scenario())
