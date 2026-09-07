"""Schema declaration checks that need no database.

The live-database assertions are in ``tests/integration/test_migrations.py``. These run
everywhere, so a schema regression is caught even when PostgreSQL is unavailable.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, Integer, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from money_machine.persistence.tables import (
    ADDENDUM_ENTITIES,
    EXPECTED_TABLES,
    WORKBOOK_ENTITIES,
    Base,
)

MIGRATIONS = Path(__file__).parents[2] / "migrations/versions"


def test_the_declared_table_set_is_exact() -> None:
    """Metadata equals the manifest in both directions: no extras, no omissions."""
    assert tuple(sorted(Base.metadata.tables)) == EXPECTED_TABLES
    assert len(EXPECTED_TABLES) == len(WORKBOOK_ENTITIES) + len(ADDENDUM_ENTITIES)


def test_the_workbook_entity_list_is_reproduced_exactly() -> None:
    """All 33 logical entities from the workbook, spelled the same way."""
    expected = [
        "shops",
        "integration_accounts",
        "workflow_runs",
        "jobs",
        "job_dependencies",
        "scheduled_triggers",
        "events",
        "idempotency_records",
        "agent_definitions",
        "agent_runs",
        "prompt_versions",
        "research_runs",
        "market_listing_observations",
        "market_shop_observations",
        "product_candidates",
        "competitor_purchases",
        "teardown_reports",
        "product_specs",
        "products",
        "product_variants",
        "notion_builds",
        "product_facts",
        "assets",
        "asset_links",
        "etsy_listings",
        "listing_versions",
        "metrics_snapshots",
        "experiments",
        "decisions",
        "incidents",
        "customer_issues",
        "artifacts",
        "receipts",
    ]

    assert list(WORKBOOK_ENTITIES) == expected
    assert set(expected) <= set(Base.metadata.tables)


def test_the_addendum_tables_carry_the_session_01_contract_fields() -> None:
    """The lineage the corrective addendum required is actually persisted."""
    columns = {name: set(table.c.keys()) for name, table in Base.metadata.tables.items()}

    assert {"prompt_reference", "prompt_sha256", "agent_definition_version"} <= columns[
        "agent_runs"
    ]
    assert {
        "idempotency_key",
        "effect_state",
        "provider_object_id",
        "reconciliation_attempt",
    } <= columns["effect_attempts"]
    assert "artifact_id" in columns["qa_result_artifacts"]
    assert "listing_package_sha256" in columns["preflight_results"]
    assert "rule_version" in columns["dedupe_results"]
    assert "compared_spec_id" in columns["dedupe_comparisons"]
    assert {"owner_type", "owner_id", "source_reference", "safe_summary"} <= columns[
        "evidence_references"
    ]
    assert {"producing_job_id", "producing_agent_run_id"} <= columns["product_specs"]
    assert {"producing_job_id", "qa_result_id"} <= columns["listing_versions"]
    assert {"artifact_id", "role", "ordinal"} <= columns["listing_version_artifacts"]
    assert {"sensitivity", "retention_class"} <= columns["artifacts"]
    assert "parent_artifact_id" in columns["artifact_lineage"]
    assert {"retry_class", "success_contract"} <= columns["jobs"]
    assert "batch_id" in columns["workflow_runs"]


@pytest.mark.parametrize("table_name", EXPECTED_TABLES)
def test_every_table_has_a_uuid_primary_key(table_name: str) -> None:
    """Identity is a UUID everywhere, with a generated default on both paths."""
    table = Base.metadata.tables[table_name]

    key = list(table.primary_key.columns)
    assert len(key) == 1, table_name
    assert isinstance(key[0].type, PgUUID)
    assert key[0].default is not None
    assert key[0].server_default is not None


@pytest.mark.parametrize("table_name", EXPECTED_TABLES)
def test_no_table_declares_a_naive_timestamp(table_name: str) -> None:
    """Every timestamp is timezone aware, so UTC is a schema guarantee."""
    table = Base.metadata.tables[table_name]

    for column in table.c:
        if column.type.__class__.__name__ == "DateTime":
            assert getattr(column.type, "timezone", False) is True, f"{table_name}.{column.name}"


def test_versioned_tables_expose_an_optimistic_version() -> None:
    """Rows with concurrent editors carry an integer version."""
    for name in ("jobs", "workflow_runs"):
        column = Base.metadata.tables[name].c["version"]
        assert isinstance(column.type, Integer)
        assert not column.nullable


def test_lineage_edges_are_foreign_keys_not_loose_identifiers() -> None:
    """A lineage claim is enforced by a foreign key wherever the target is a real table."""
    tables = Base.metadata.tables

    assert any(
        isinstance(constraint, ForeignKeyConstraint)
        and constraint.referred_table.name == "prompt_versions"
        for constraint in tables["agent_runs"].constraints
    )
    assert any(
        isinstance(constraint, ForeignKeyConstraint) and constraint.referred_table.name == "jobs"
        for constraint in tables["artifacts"].constraints
    )
    assert any(
        isinstance(constraint, ForeignKeyConstraint)
        and constraint.referred_table.name == "agent_runs"
        for constraint in tables["artifacts"].constraints
    )


def test_idempotency_and_hash_uniqueness_are_declared() -> None:
    """Each at-most-once claim has a uniqueness constraint behind it."""
    expected = {
        "jobs": {"idempotency_key"},
        "events": {"dedupe_key"},
        "idempotency_records": {"idempotency_key"},
        "listing_versions": {"package_sha256"},
        "prompt_versions": {"sha256"},
        "competitor_purchases": {"idempotency_key"},
    }

    for table_name, columns in expected.items():
        unique_sets = [
            {column.name for column in constraint.columns}
            for constraint in Base.metadata.tables[table_name].constraints
            if isinstance(constraint, UniqueConstraint)
        ]
        assert columns in unique_sets, f"{table_name} is missing a unique constraint on {columns}"


def test_taxonomy_constraints_are_table_level_so_migrations_carry_them() -> None:
    """A column-level CHECK would be silently dropped by Alembic's autogenerate."""
    for table in Base.metadata.tables.values():
        for column in table.c:
            assert not [
                constraint
                for constraint in column.constraints
                if isinstance(constraint, CheckConstraint)
            ], f"{table.name}.{column.name} holds a column-level CHECK"

    checks = {
        constraint.name
        for table in Base.metadata.tables.values()
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_jobs_status_taxonomy" in checks
    assert len(checks) > 60


def test_exactly_one_migration_revision_exists_and_it_is_the_root() -> None:
    """The foundation ships one reviewed initial revision, not a chain of fixups."""
    revisions = sorted(path for path in MIGRATIONS.glob("*.py"))

    assert len(revisions) == 1
    body = revisions[0].read_text(encoding="utf-8")
    assert "down_revision: str | None = None" in body
    assert body.count("op.create_table") == len(EXPECTED_TABLES)
    assert body.count("op.drop_table") == len(EXPECTED_TABLES)
    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto" in body


def test_contract_taxonomies_are_subsets_of_their_table_taxonomies() -> None:
    """A valid contract instance must be persistable: no vocabulary may disagree."""
    from money_machine.domain.enums import (
        AgentRunStatus,
        AutonomyMode,
        JobStatus,
        ProductLifecycleState,
        RetryClass,
        SideEffectClass,
    )
    from money_machine.persistence.tables import (
        DEDUPE_OUTCOMES,
        EFFECT_STATES,
        INCIDENT_STATES,
        QA_OUTCOMES,
    )

    incident_status_values = {"OPEN", "BLOCKED", "RESOLVED", "UNCERTAIN_EXTERNAL_EFFECT"}
    assert incident_status_values <= set(INCIDENT_STATES)
    assert set(DEDUPE_OUTCOMES) == {"PASS", "TOO_CLOSE"}
    assert set(QA_OUTCOMES) == {"PASS", "FAIL"}
    assert set(EFFECT_STATES) == {"CONFIRMED", "ABSENT", "UNKNOWN"}

    for enum_type, table, column in (
        (JobStatus, "jobs", "status"),
        (SideEffectClass, "jobs", "side_effect_class"),
        (RetryClass, "jobs", "retry_class"),
        (AutonomyMode, "jobs", "allowed_mode"),
        (ProductLifecycleState, "workflow_runs", "product_state"),
        (AgentRunStatus, "agent_runs", "status"),
    ):
        constraint = next(
            item
            for item in Base.metadata.tables[table].constraints
            if isinstance(item, CheckConstraint) and item.name == f"ck_{table}_{column}_taxonomy"
        )
        rendered = str(constraint.sqltext)
        for member in enum_type:
            assert f"'{member.value}'" in rendered, f"{table}.{column} rejects {member.value}"


def test_optimistic_locking_is_configured_on_versioned_tables() -> None:
    """An in-memory comparison is not a guard; the mapper must add the version predicate."""
    from money_machine.persistence.tables import Job, WorkflowRun

    for model in (Job, WorkflowRun):
        column = model.__mapper__.version_id_col
        assert column is not None, model.__tablename__
        assert column.name == "version"


def test_append_only_tables_are_declared_with_their_ddl() -> None:
    """The trigger SQL is declared once and used by both the migration and the tests."""
    from money_machine.persistence.tables import (
        APPEND_ONLY_FUNCTION_SQL,
        APPEND_ONLY_TABLES,
        append_only_trigger_sql,
    )

    assert set(APPEND_ONLY_TABLES) == {"events", "receipts"}
    assert "RAISE EXCEPTION" in APPEND_ONLY_FUNCTION_SQL
    for table in APPEND_ONLY_TABLES:
        sql = append_only_trigger_sql(table)
        assert "BEFORE UPDATE OR DELETE" in sql
        assert table in sql


def test_the_migration_installs_the_triggers_and_leaves_pgcrypto_on_downgrade() -> None:
    """Alembic does not autogenerate triggers, so the revision must install them."""
    revision = next(MIGRATIONS.glob("*.py")).read_text(encoding="utf-8")
    upgrade_body, downgrade_body = revision.split("def downgrade() -> None:")

    assert "install_append_only_triggers(op.execute)" in upgrade_body
    assert "drop_append_only_triggers(op.execute)" in downgrade_body
    assert revision.count("CREATE EXTENSION IF NOT EXISTS pgcrypto") == 1
