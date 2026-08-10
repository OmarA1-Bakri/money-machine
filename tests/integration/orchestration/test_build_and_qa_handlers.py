from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select

from money_machine.application.services.product_service import ProductService
from money_machine.domain.models.product_spec import DedupeResult, ProductFact, ProductSpec
from money_machine.integrations.notion.fixture_adapter import LocalNotionAdapter
from money_machine.persistence.database import Database
from money_machine.persistence.tables import product_qa_results
from money_machine.persistence.unit_of_work import UnitOfWork

WORKFLOW_ID = UUID("00000000-0000-0000-0000-000000000006")


@pytest.fixture(scope="module", autouse=True)
def migrated_database() -> None:
    url = os.environ["MONEY_MACHINE_TEST_DATABASE_URL"]
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


def _spec() -> ProductSpec:
    return ProductSpec(
        product_spec_id="spec-handler",
        candidate_id="candidate-handler",
        identity_niche="Freelance Designers",
        base_category="Client Portal",
        target_buyer="People managing Freelance Designers",
        promised_outcome="A structured Client Portal workspace",
        hubs=("Home", "Clients", "Projects", "Content", "Invoices", "Tasks", "Notes"),
        colour_variants=("Ink", "Clay", "Moss", "Sky"),
        features=("project stages", "invoice tracking", "client notes"),
        product_facts=(
            ProductFact(
                claim="Configured with 7 hubs",
                category="HUB_INVENTORY",
                evidence_ids=("evidence-handler",),
            ),
            ProductFact(
                claim="Includes project stages",
                category="FEATURE",
                evidence_ids=("evidence-handler",),
            ),
            ProductFact(
                claim="Includes invoice tracking",
                category="FEATURE",
                evidence_ids=("evidence-handler",),
            ),
            ProductFact(
                claim="Includes client notes",
                category="FEATURE",
                evidence_ids=("evidence-handler",),
            ),
            ProductFact(
                claim="Configured with 4 colour variants",
                category="COLOUR_VARIANTS",
                evidence_ids=("evidence-handler",),
            ),
            ProductFact(
                claim="People managing Freelance Designers",
                category="BUYER_FIT",
                evidence_ids=("evidence-handler",),
            ),
            ProductFact(
                claim="A structured Client Portal workspace",
                category="WORKFLOW_OUTCOME",
                evidence_ids=("evidence-handler",),
            ),
        ),
        source_evidence_ids=("evidence-handler",),
        spec_sha256="3" * 64,
    )


def _dedupe(*, passed: bool = True, product_spec_id: str = "spec-handler") -> DedupeResult:
    return DedupeResult(
        dedupe_result_id="dedupe-handler",
        product_spec_id=product_spec_id,
        passed=passed,
        matched_product_spec_ids=() if passed else ("existing-spec",),
        reasons=("no catalogue collision",) if passed else ("catalogue collision",),
        result_sha256="4" * 64,
    )


def test_build_and_qa_handlers_use_workflow_scoped_local_destination(tmp_path: Path) -> None:
    service = ProductService(
        artifact_root=tmp_path / "runtime/artifacts",
        builder=LocalNotionAdapter(),
        clock=lambda: datetime(2026, 8, 9, 12, tzinfo=UTC),
    )

    build = service.build_local_product(_spec(), _dedupe(), WORKFLOW_ID)
    qa = service.run_product_qa(build)

    assert (
        Path(build.root_artifact_path)
        == (tmp_path / "runtime/artifacts" / str(WORKFLOW_ID) / "product").resolve()
    )
    assert build.product_spec_id == "spec-handler"
    assert qa.build_id == build.build_id
    assert qa.passed is True
    assert qa.findings == ()


def test_r5_behavior_contract_handlers_persist_exact_lineage(tmp_path: Path) -> None:
    try:
        service = ProductService(
            artifact_root=tmp_path / "runtime/artifacts", builder=LocalNotionAdapter()
        )
        build = service.build_local_product(_spec(), _dedupe(), WORKFLOW_ID)
        qa = service.run_product_qa(build)
    except Exception as error:  # skeleton-stage assertion, removed by real behavior
        pytest.fail(f"handler behavior is not implemented: {error}")

    assert build.product_spec_id == _spec().product_spec_id
    assert qa.build_id == build.build_id
    assert ProductService.successor_allowed(qa) is True


@pytest.mark.parametrize(
    "dedupe",
    [_dedupe(passed=False), _dedupe(product_spec_id="different-spec")],
)
def test_build_handler_rejects_nonapproved_or_mismatched_dedupe_before_writing(
    tmp_path: Path, dedupe: DedupeResult
) -> None:
    artifact_root = tmp_path / "runtime/artifacts"
    service = ProductService(artifact_root=artifact_root, builder=LocalNotionAdapter())

    with pytest.raises(ValueError, match="dedupe-approved ProductSpec"):
        service.build_local_product(_spec(), dedupe, WORKFLOW_ID)

    assert not artifact_root.exists()


def test_qa_handler_exposes_no_successor_signal_for_a_failed_bundle(tmp_path: Path) -> None:
    service = ProductService(
        artifact_root=tmp_path / "runtime/artifacts", builder=LocalNotionAdapter()
    )
    build = service.build_local_product(_spec(), _dedupe(), WORKFLOW_ID)
    (Path(build.root_artifact_path) / "README.md").write_text("changed", encoding="utf-8")

    qa = service.run_product_qa(build)

    assert qa.passed is False
    assert service.successor_allowed(qa) is False


def test_durable_handlers_load_and_persist_exact_predecessor_results(
    tmp_path: Path,
) -> None:
    asyncio.run(_assert_durable_handlers(tmp_path))


def test_r5_behavior_contract_durable_handlers_round_trip(tmp_path: Path) -> None:
    try:
        asyncio.run(_assert_durable_handlers(tmp_path, identity_suffix="-r5"))
    except Exception as error:  # skeleton-stage assertion, removed by real behavior
        pytest.fail(f"durable handler behavior is not implemented: {error}")


async def _assert_durable_handlers(tmp_path: Path, identity_suffix: str = "") -> None:
    spec = _spec().model_copy(update={"product_spec_id": f"spec-handler{identity_suffix}"})
    dedupe = _dedupe().model_copy(
        update={
            "dedupe_result_id": f"dedupe-handler{identity_suffix}",
            "product_spec_id": spec.product_spec_id,
        }
    )
    workflow_id = (
        WORKFLOW_ID if not identity_suffix else UUID("00000000-0000-0000-0000-000000000007")
    )
    database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
    service = ProductService(
        artifact_root=tmp_path / "runtime/artifacts",
        builder=LocalNotionAdapter(),
        clock=lambda: datetime(2026, 8, 9, 12, tzinfo=UTC),
    )
    try:
        async with UnitOfWork(database) as uow:
            await uow.products.add_spec(spec)
            await uow.products.add_dedupe(dedupe)

        build = await service.handle_build_local_product(
            database=database,
            product_spec_id=spec.product_spec_id,
            dedupe_result_id=dedupe.dedupe_result_id,
            workflow_run_id=workflow_id,
        )
        async with UnitOfWork(database) as uow:
            stored_build = await uow.products.get_build(build.build_id)
        assert stored_build == build

        qa = await service.handle_run_product_qa(database=database, build_id=build.build_id)
        async with database.session_factory() as session:
            payload = (
                await session.execute(
                    select(product_qa_results.c.payload).where(
                        product_qa_results.c.product_qa_result_id == qa.qa_result_id
                    )
                )
            ).scalar_one()
        assert payload == json.loads(qa.model_dump_json())
        assert qa.build_id == build.build_id
        assert qa.passed is True
    finally:
        await database.dispose()
