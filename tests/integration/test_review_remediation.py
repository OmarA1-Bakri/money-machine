"""Regression tests for the Session 02 closure-review findings.

Each test corresponds to a defect an independent reviewer demonstrated against an earlier
revision of this schema. They exist so those defects cannot come back quietly.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from money_machine.domain.enums import ProductLifecycleState
from money_machine.persistence.repositories._base import ConcurrentModificationError
from money_machine.persistence.repositories.workflows import WorkflowRunRepository
from money_machine.persistence.seed import seed
from money_machine.persistence.tables import AgentDefinition, EvidenceReference, PromptVersion
from tests.integration.factories import (
    make_agent_run,
    make_artifact,
    make_evidence,
    make_job,
    make_shop,
    make_workflow,
)


async def test_evidence_citations_are_persistable_and_linked(session: AsyncSession) -> None:
    """C1: thirteen contracts require evidence, so evidence needs a home."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await make_job(session, workflow)
    run = await make_agent_run(session, job)
    artifact = await make_artifact(session, job, run)

    evidence = await make_evidence(session, owner_type="agent_runs", owner_id=run.id)
    evidence.artifact_id = artifact.id
    evidence.producing_job_id = job.id
    await session.flush()

    found = (
        (
            await session.execute(
                select(EvidenceReference).where(EvidenceReference.owner_id == run.id)
            )
        )
        .scalars()
        .all()
    )
    assert [row.id for row in found] == [evidence.id]
    assert found[0].artifact_id == artifact.id

    with pytest.raises(IntegrityError):
        await make_evidence(
            session,
            owner_type="agent_runs",
            owner_id=run.id,
            source_reference=evidence.source_reference,
        )


async def test_evidence_owner_type_is_constrained(session: AsyncSession) -> None:
    """An evidence row cannot cite a table that may not carry evidence."""
    shop = await make_shop(session)

    with pytest.raises((IntegrityError, DBAPIError)):
        await make_evidence(session, owner_type="not_a_table", owner_id=shop.id)


async def test_a_concurrent_writer_cannot_lose_an_update(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """C2: two writers on one row must not silently overwrite one another."""
    async with session_factory() as setup:
        shop = await make_shop(setup)
        workflow = await make_workflow(setup, shop)
        workflow_id = workflow.id
        await setup.commit()

    async with session_factory() as first, session_factory() as second:
        first_row = await WorkflowRunRepository(first).require(workflow_id)
        second_row = await WorkflowRunRepository(second).require(workflow_id)
        assert first_row.version == second_row.version == 1

        await WorkflowRunRepository(first).update_versioned(
            first_row,
            expected_version=1,
            product_state=ProductLifecycleState.RESEARCHING.value,
        )
        await first.commit()

        with pytest.raises(ConcurrentModificationError):
            await WorkflowRunRepository(second).update_versioned(
                second_row,
                expected_version=1,
                product_state=ProductLifecycleState.REJECTED.value,
            )
        await second.rollback()

    async with session_factory() as check:
        final = await WorkflowRunRepository(check).require(workflow_id)
        assert final.product_state == ProductLifecycleState.RESEARCHING.value
        assert final.version == 2


async def test_qa_and_dedupe_relations_reject_dangling_identifiers(
    engine: AsyncEngine,
) -> None:
    """H4: a verdict cannot name an artifact or specification that does not exist."""
    async with engine.begin() as connection:
        with pytest.raises(DBAPIError):
            await connection.execute(
                text(
                    "INSERT INTO qa_result_artifacts (id, qa_result_id, artifact_id)"
                    " VALUES (gen_random_uuid(), gen_random_uuid(), gen_random_uuid())"
                )
            )
    async with engine.begin() as connection:
        with pytest.raises(DBAPIError):
            await connection.execute(
                text(
                    "INSERT INTO dedupe_comparisons (id, dedupe_result_id, compared_spec_id)"
                    " VALUES (gen_random_uuid(), gen_random_uuid(), gen_random_uuid())"
                )
            )


async def test_an_agent_run_cannot_misreport_its_agent_or_prompt(
    session: AsyncSession,
) -> None:
    """H5: the denormalised lineage is bound by composite foreign keys."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await make_job(session, workflow)
    run = await make_agent_run(session, job)

    run.prompt_sha256 = "e" * 64

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_an_agent_run_cannot_claim_a_wrong_agent_id(session: AsyncSession) -> None:
    """The same guard applies to the agent identifier and its contract version."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await make_job(session, workflow)
    run = await make_agent_run(session, job)

    run.agent_id = "A07"

    with pytest.raises(IntegrityError):
        await session.flush()


async def test_a_decision_without_a_type_cannot_smuggle_a_successor(
    engine: AsyncEngine,
) -> None:
    """H7: SQL three-valued logic must not let a NULL decision bypass the rule."""
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO shops (id, name, connection_state, timezone, active)"
                " VALUES (gen_random_uuid(), 'h7', 'UNCONNECTED', 'UTC', true)"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO workflow_runs"
                " (id, shop_id, workflow_type, workflow_version, product_state, started_at,"
                "  version)"
                " SELECT gen_random_uuid(), id, 'W', 1, 'DISCOVERED', now(), 1"
                " FROM shops WHERE name = 'h7'"
            )
        )
        await connection.execute(
            text(
                "INSERT INTO jobs (id, workflow_id, job_type, object_type, object_id,"
                " owner_agent_id, status, input, success_contract, scheduled_at, attempt,"
                " max_attempts, idempotency_key, side_effect_class, retry_class, allowed_mode,"
                " version)"
                " SELECT gen_random_uuid(), id, 'J', 'workflow_runs', id, 'A01', 'READY',"
                " '{}', '{}', now(), 0, 3, 'k-h7', 'NONE', 'SAFE', 'simulation', 1"
                " FROM workflow_runs LIMIT 1"
            )
        )
        with pytest.raises(DBAPIError, match="only_multiply_has_a_successor"):
            await connection.execute(
                text(
                    "INSERT INTO decisions (id, workflow_id, job_id, decision_type, decision,"
                    " rule_version, explanation, successor_workflow_id, decided_at)"
                    " SELECT gen_random_uuid(), w.id, j.id, 'portfolio', NULL, 'v1', 'x',"
                    " gen_random_uuid(), now()"
                    " FROM workflow_runs w JOIN jobs j ON j.workflow_id = w.id LIMIT 1"
                )
            )


async def test_a_reconcept_specification_must_cite_its_parent(engine: AsyncEngine) -> None:
    """M15: only ORIGINAL may omit parent lineage."""
    async with engine.begin() as connection:
        with pytest.raises(DBAPIError, match="reconcept_cites_its_parent_spec"):
            await connection.execute(
                text(
                    "INSERT INTO product_specs (id, product_id, workflow_id, version,"
                    " producing_job_id, producing_agent_run_id, lineage_kind, identity,"
                    " base_category, buyer_problem, title, tier, real_price, anchor_price,"
                    " currency, hubs, colour_variants, features, experiment_plan,"
                    " concept_fingerprint, rule_version)"
                    " VALUES (gen_random_uuid(), gen_random_uuid(), gen_random_uuid(), 1,"
                    " gen_random_uuid(), gen_random_uuid(), 'RECONCEPT', 'i', 'c', 'b', 't',"
                    " 'core', 1, 2, 'USD', '[]', '[]', '[]', 'e', repeat('a', 64), 'v1')"
                )
            )


async def test_currency_codes_and_large_artifacts_are_handled(engine: AsyncEngine) -> None:
    """L19: currency is ISO 4217 and an artifact may exceed two gigabytes."""
    async with engine.begin() as connection:
        with pytest.raises(DBAPIError, match="currency_is_iso4217"):
            await connection.execute(
                text(
                    "INSERT INTO metrics_snapshots (id, listing_id, listing_version_id, job_id,"
                    " window_start, window_end, views, favourites, sales, revenue, currency,"
                    " live_days, reconciled, captured_at)"
                    " VALUES (gen_random_uuid(), gen_random_uuid(), gen_random_uuid(),"
                    " gen_random_uuid(), now() - interval '1 day', now(), 0, 0, 0, 0, 'zz9',"
                    " 0, false, now())"
                )
            )
    async with engine.connect() as connection:
        size = (
            await connection.execute(
                text(
                    "SELECT data_type FROM information_schema.columns"
                    " WHERE table_name = 'artifacts' AND column_name = 'byte_size'"
                )
            )
        ).scalar_one()
    assert size == "bigint"


async def test_seed_converges_a_drifted_row(session: AsyncSession, repository_root: Path) -> None:
    """M10: a hand-edited row must not outrank the YAML authority."""
    await seed(session, repository_root=repository_root)
    await session.commit()
    agent = (
        (await session.execute(select(AgentDefinition).where(AgentDefinition.agent_id == "A01")))
        .scalars()
        .one()
    )
    agent.name = "TAMPERED"
    agent.timeout_seconds = 1
    agent.commissioning_state = "TESTED"
    await session.commit()

    report = await seed(session, repository_root=repository_root)
    await session.commit()

    assert report.total_created == 0
    assert report.agents_corrected == 1
    assert report.changed
    restored = (
        (await session.execute(select(AgentDefinition).where(AgentDefinition.agent_id == "A01")))
        .scalars()
        .one()
    )
    assert restored.name == "Shop Orchestrator"
    assert restored.commissioning_state == "DESIGNED"
    assert restored.timeout_seconds == 300


async def test_seed_repairs_a_renamed_prompt_reference(
    session: AsyncSession,
    repository_root: Path,
) -> None:
    """M12: a moved prompt file must not leave an unlocatable reference."""
    await seed(session, repository_root=repository_root)
    await session.commit()
    row = (
        (await session.execute(select(PromptVersion).order_by(PromptVersion.source_path).limit(1)))
        .scalars()
        .one()
    )
    original_path = row.source_path
    row.source_path = "prompts/implementation/moved_away.md"
    row.prompt_reference = "prompt://moved_away"
    await session.commit()

    report = await seed(session, repository_root=repository_root)
    await session.commit()

    assert report.prompt_versions_created == 0
    assert report.prompt_versions_corrected == 1
    repaired = (
        (await session.execute(select(PromptVersion).where(PromptVersion.sha256 == row.sha256)))
        .scalars()
        .one()
    )
    assert repaired.source_path == original_path


async def test_concurrent_seeding_converges_without_error(
    session_factory: async_sessionmaker[AsyncSession],
    repository_root: Path,
) -> None:
    """M11: two processes seeding at once both succeed."""

    async def run_seed() -> int:
        async with session_factory() as session:
            report = await seed(session, repository_root=repository_root)
            await session.commit()
            return report.total_created

    results = await asyncio.gather(run_seed(), run_seed(), run_seed())

    assert sum(results) > 0
    async with session_factory() as check:
        agents = (
            await check.execute(select(func.count()).select_from(AgentDefinition))
        ).scalar_one()
        prompts = (
            await check.execute(select(func.count()).select_from(PromptVersion))
        ).scalar_one()
    assert agents == 16
    assert prompts == 18  # 16 impl + A01 + A02 agent prompts


async def test_an_orphan_table_is_reported_as_drift(
    migrated_url: str,
    repository_root: Path,
    engine: AsyncEngine,
) -> None:
    """M14: a table that is no longer declared must not hide from `alembic check`."""
    from concurrent.futures import ThreadPoolExecutor

    from alembic import command
    from alembic.config import Config
    from alembic.util.exc import AutogenerateDiffsDetected

    async with engine.begin() as connection:
        await connection.execute(text("CREATE TABLE orphan_from_another_branch (id uuid)"))

    def run_check() -> None:
        config = Config(str(repository_root / "alembic.ini"))
        config.set_main_option("script_location", str(repository_root / "migrations"))
        config.set_main_option("sqlalchemy.url", migrated_url)
        command.check(config)

    with (
        ThreadPoolExecutor(max_workers=1) as pool,
        pytest.raises(AutogenerateDiffsDetected, match="orphan_from_another_branch"),
    ):
        pool.submit(run_check).result()
