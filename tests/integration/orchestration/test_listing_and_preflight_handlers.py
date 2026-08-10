import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select

from money_machine.agents.contracts.creative_assets import CreativeAssetRequest
from money_machine.agents.contracts.merchandising import MerchandisingRequest
from money_machine.agents.contracts.preflight import PreflightRequest
from money_machine.agents.implementations.creative_assets import handle_creative_assets
from money_machine.agents.implementations.merchandising import handle_merchandising
from money_machine.agents.implementations.preflight import handle_preflight
from money_machine.domain.models.listing import PreflightResult
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import ProductFact, ProductSpec
from money_machine.persistence.database import Database
from money_machine.persistence.tables import metadata, preflight_results
from money_machine.persistence.unit_of_work import UnitOfWork

SHA = "a" * 64


def spec() -> ProductSpec:
    return ProductSpec(
        product_spec_id="spec-1",
        candidate_id="candidate-1",
        identity_niche="adhd students",
        base_category="digital planner",
        target_buyer="People managing adhd students",
        promised_outcome="A structured digital planner workspace",
        hubs=("Home", "Courses", "Tasks", "Notes", "Reviews", "Archive"),
        colour_variants=("Ink", "Sand", "Sage"),
        features=("Linked course and task views",),
        product_facts=(
            ProductFact(
                claim="Configured with 6 hubs",
                category="HUB_INVENTORY",
                evidence_ids=("evidence-1",),
            ),
            ProductFact(
                claim="Includes Linked course and task views",
                category="FEATURE",
                evidence_ids=("evidence-1",),
            ),
            ProductFact(
                claim="Configured with 3 colour variants",
                category="COLOUR_VARIANTS",
                evidence_ids=("evidence-1",),
            ),
            ProductFact(
                claim="People managing adhd students",
                category="BUYER_FIT",
                evidence_ids=("evidence-1",),
            ),
            ProductFact(
                claim="A structured digital planner workspace",
                category="WORKFLOW_OUTCOME",
                evidence_ids=("evidence-1",),
            ),
        ),
        source_evidence_ids=("evidence-1",),
        spec_sha256=SHA,
    )


def build() -> BuildResult:
    return BuildResult(
        build_id="build-1",
        product_spec_id="spec-1",
        root_artifact_path="products/spec-1",
        artifacts=(),
        manifest_sha256=SHA,
        renderer_version="1",
    )


def qa() -> ProductQAResult:
    return ProductQAResult(
        qa_result_id="qa-1",
        build_id="build-1",
        passed=True,
        findings=(),
        checked_at=datetime(2026, 8, 9, tzinfo=UTC),
        result_sha256=SHA,
    )


def test_handlers_persist_and_round_trip_a_draft_ready_package(tmp_path: Path) -> None:
    async def scenario() -> None:
        database_url = os.environ["MONEY_MACHINE_TEST_DATABASE_URL"]
        database = Database.from_url(database_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
        async with UnitOfWork(database) as unit_of_work:
            await unit_of_work.products.add_spec(spec())
            await unit_of_work.products.add_build(build())
            await unit_of_work.products.add_qa(qa())
        listing = handle_merchandising(MerchandisingRequest(spec=spec(), build=build(), qa=qa()))
        rendered = await handle_creative_assets(
            CreativeAssetRequest(
                package=listing.package,
                spec=spec(),
                build=build(),
                qa=qa(),
                destination=tmp_path,
                database_url=database_url,
            )
        )
        preflight = await handle_preflight(
            PreflightRequest(
                package=rendered.package,
                qa=qa(),
                spec=spec(),
                build=build(),
                artifact_root=tmp_path,
                database_url=database_url,
                checked_at=datetime(2026, 8, 9, 12, tzinfo=UTC),
            )
        )

        async with UnitOfWork(database) as unit_of_work:
            stored = await unit_of_work.listings.get_package(rendered.package.listing_package_id)
            assert unit_of_work.session is not None
            row = await unit_of_work.session.execute(
                select(preflight_results.c.payload).where(
                    preflight_results.c.preflight_result_id == preflight.result.preflight_result_id
                )
            )
            stored_preflight = PreflightResult.model_validate_json(
                json.dumps(row.scalar_one(), separators=(",", ":"))
            )
        await database.dispose()

        assert listing.event_name == "LISTING_PACKAGE_CREATED"
        assert all(record.source != "REJECTED" for record in listing.claim_records)
        assert rendered.event_name == "ASSET_QA_PASSED"
        assert preflight.event_name == "DRAFT_READY"
        assert preflight.result.passed is True
        assert preflight.successor_job_type is None
        assert stored == rendered.package
        assert stored_preflight == preflight.result

    asyncio.run(scenario())
