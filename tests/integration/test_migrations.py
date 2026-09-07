"""Migrations must build exactly the declared schema, and must reverse."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from money_machine.persistence.tables import (
    ADDENDUM_ENTITIES,
    EXPECTED_TABLES,
    WORKBOOK_ENTITIES,
    Base,
)
from tests.integration.alembic_support import downgrade, upgrade

TABLE_QUERY = text(
    "SELECT table_name FROM information_schema.tables"
    " WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
)


async def live_tables(engine: AsyncEngine) -> set[str]:
    """The base tables actually present in the database."""
    async with engine.connect() as connection:
        rows = (await connection.execute(TABLE_QUERY)).scalars().all()
    return set(rows)


def test_declared_schema_covers_the_workbook_and_the_addendum() -> None:
    """The manifest is the workbook's 33 entities plus the addendum's additions."""
    assert len(WORKBOOK_ENTITIES) == 33
    assert len(set(WORKBOOK_ENTITIES)) == 33
    assert set(EXPECTED_TABLES) == set(WORKBOOK_ENTITIES) | set(ADDENDUM_ENTITIES)
    assert not set(WORKBOOK_ENTITIES) & set(ADDENDUM_ENTITIES)
    assert tuple(sorted(Base.metadata.tables)) == EXPECTED_TABLES
    for required in (
        "effect_attempts",
        "qa_results",
        "preflight_results",
        "dedupe_results",
        "evidence_references",
        "qa_result_artifacts",
        "dedupe_comparisons",
        "listing_version_artifacts",
    ):
        assert required in ADDENDUM_ENTITIES


async def test_upgrade_creates_exactly_the_declared_tables(engine: AsyncEngine) -> None:
    """An empty database upgraded to head holds the declared set and nothing else."""
    present = await live_tables(engine)

    assert present - {"alembic_version"} == set(EXPECTED_TABLES)


async def test_downgrade_to_base_then_upgrade_again_is_clean(
    migrated_url: str,
    repository_root: Path,
    engine: AsyncEngine,
) -> None:
    """Migrations reverse fully and re-apply, so a bad revision is recoverable."""
    await asyncio.to_thread(downgrade, migrated_url, repository_root)
    assert await live_tables(engine) - {"alembic_version"} == set()

    await asyncio.to_thread(upgrade, migrated_url, repository_root)
    assert await live_tables(engine) - {"alembic_version"} == set(EXPECTED_TABLES)


async def test_every_table_has_a_uuid_primary_key_and_utc_timestamps(
    engine: AsyncEngine,
) -> None:
    """UUID keys and timezone-aware timestamps are schema conventions, not intentions."""
    async with engine.connect() as connection:
        keys = (
            await connection.execute(
                text(
                    "SELECT t.table_name, c.data_type FROM information_schema.tables t"
                    " JOIN information_schema.table_constraints k"
                    "   ON k.table_name = t.table_name AND k.constraint_type = 'PRIMARY KEY'"
                    " JOIN information_schema.key_column_usage u"
                    "   ON u.constraint_name = k.constraint_name"
                    " JOIN information_schema.columns c"
                    "   ON c.table_name = t.table_name AND c.column_name = u.column_name"
                    " WHERE t.table_schema = 'public' AND t.table_name <> 'alembic_version'"
                )
            )
        ).all()
        naive = (
            await connection.execute(
                text(
                    "SELECT table_name, column_name FROM information_schema.columns"
                    " WHERE table_schema = 'public'"
                    "   AND data_type = 'timestamp without time zone'"
                )
            )
        ).all()

    assert {row[0] for row in keys} == set(EXPECTED_TABLES)
    assert all(row[1] == "uuid" for row in keys), [row for row in keys if row[1] != "uuid"]
    assert naive == [], f"naive timestamps found: {naive}"


async def test_ready_and_due_job_indexes_exist(engine: AsyncEngine) -> None:
    """The orchestrator's hot queries have partial indexes, not table scans."""
    async with engine.connect() as connection:
        indexes = (
            (
                await connection.execute(
                    text("SELECT indexname FROM pg_indexes WHERE tablename = 'jobs'")
                )
            )
            .scalars()
            .all()
        )

    assert "ix_jobs_ready_due" in indexes
    assert "ix_jobs_lease_expiry" in indexes


@pytest.mark.parametrize(
    ("table", "constraint"),
    [
        ("jobs", "uq_jobs_idempotency_key"),
        ("events", "uq_events_dedupe_key"),
        ("idempotency_records", "uq_idempotency_records_idempotency_key"),
        ("listing_versions", "uq_listing_versions_package_sha256"),
        ("prompt_versions", "uq_prompt_versions_sha256"),
    ],
)
async def test_idempotency_and_immutability_constraints_are_live(
    engine: AsyncEngine,
    table: str,
    constraint: str,
) -> None:
    """Each uniqueness claim exists in the database catalogue, not only in Python."""
    async with engine.connect() as connection:
        names = (
            (
                await connection.execute(
                    text(
                        "SELECT constraint_name FROM information_schema.table_constraints"
                        " WHERE table_name = :table AND constraint_type = 'UNIQUE'"
                    ),
                    {"table": table},
                )
            )
            .scalars()
            .all()
        )

    assert constraint in names


async def test_every_declared_check_constraint_is_live(engine: AsyncEngine) -> None:
    """Taxonomy and invariant checks reach the database."""
    async with engine.connect() as connection:
        checks = (
            (
                await connection.execute(
                    text(
                        "SELECT conname FROM pg_constraint c"
                        " JOIN pg_class t ON t.oid = c.conrelid"
                        " WHERE c.contype = 'c' AND t.relname = ANY(:tables)"
                    ),
                    {"tables": list(EXPECTED_TABLES)},
                )
            )
            .scalars()
            .all()
        )

    live = set(checks)
    for expected in (
        "ck_jobs_status_taxonomy",
        "ck_jobs_attempt_within_budget",
        "ck_product_specs_anchor_at_least_real_price",
        "ck_product_specs_successor_starts_a_new_workflow",
        "ck_effect_attempts_effect_state_evidence",
        "ck_agent_definitions_commissioned_requires_evidence",
        "ck_listing_versions_digital_delivery_only",
        "ck_qa_results_checks_is_an_array",
        "ck_config_references_never_authoritative",
        "ck_teardown_reports_never_copy_protected_content",
        "ck_decisions_multiply_creates_a_new_workflow",
    ):
        assert expected in live, f"{expected} missing from {sorted(live)}"


async def test_append_only_tables_refuse_updates_and_deletes(engine: AsyncEngine) -> None:
    """`events` and `receipts` are documented immutable, so the database enforces it."""
    async with engine.begin() as connection:
        triggers = (
            (
                await connection.execute(
                    text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal ORDER BY tgname")
                )
            )
            .scalars()
            .all()
        )

    assert set(triggers) == {"events_are_append_only", "receipts_are_append_only"}


async def test_downgrade_removes_the_append_only_triggers(
    migrated_url: str,
    repository_root: Path,
    engine: AsyncEngine,
) -> None:
    """A reversal leaves no trigger or function behind."""
    await asyncio.to_thread(downgrade, migrated_url, repository_root)

    async with engine.connect() as connection:
        triggers = (
            await connection.execute(text("SELECT count(*) FROM pg_trigger WHERE NOT tgisinternal"))
        ).scalar_one()
        functions = (
            await connection.execute(
                text("SELECT count(*) FROM pg_proc WHERE proname = 'money_machine_refuse_mutation'")
            )
        ).scalar_one()

    assert triggers == 0
    assert functions == 0

    await asyncio.to_thread(upgrade, migrated_url, repository_root)


async def test_alembic_check_reports_no_drift(migrated_url: str, repository_root: Path) -> None:
    """The migration and the declared metadata agree, in both directions."""
    from concurrent.futures import ThreadPoolExecutor

    from alembic import command
    from alembic.config import Config
    from alembic.util.exc import AutogenerateDiffsDetected

    def run_check() -> None:
        config = Config(str(repository_root / "alembic.ini"))
        config.set_main_option("script_location", str(repository_root / "migrations"))
        config.set_main_option("sqlalchemy.url", migrated_url)
        command.check(config)

    with ThreadPoolExecutor(max_workers=1) as pool:
        try:
            pool.submit(run_check).result()
        except AutogenerateDiffsDetected as error:  # pragma: no cover - failure path
            raise AssertionError(f"schema drift: {error}") from error
