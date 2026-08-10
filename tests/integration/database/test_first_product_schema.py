from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import create_async_engine

from money_machine.domain.value_objects import canonical_sha256
from money_machine.persistence.tables import metadata as schema_metadata

EXPECTED_TABLES = {
    "workflow_runs",
    "jobs",
    "job_dependencies",
    "job_attempts",
    "domain_events",
    "artifacts",
    "evidence_references",
    "research_packets",
    "research_observations",
    "candidates",
    "qualification_scores",
    "candidate_shortlists",
    "product_specs",
    "dedupe_results",
    "build_results",
    "product_qa_results",
    "listing_packages",
    "preflight_results",
}
EXPECTED_PRIMARY_KEYS = {
    "workflow_runs": ("workflow_run_id",),
    "jobs": ("job_id",),
    "job_dependencies": ("job_id", "depends_on_job_id"),
    "job_attempts": ("job_id", "attempt_number"),
    "domain_events": ("event_id",),
    "artifacts": ("artifact_id",),
    "evidence_references": ("evidence_id",),
    "research_packets": ("packet_id",),
    "research_observations": ("observation_id",),
    "candidates": ("candidate_id",),
    "qualification_scores": ("qualification_score_id",),
    "candidate_shortlists": ("shortlist_id",),
    "product_specs": ("product_spec_id",),
    "dedupe_results": ("dedupe_result_id",),
    "build_results": ("build_id",),
    "product_qa_results": ("product_qa_result_id",),
    "listing_packages": ("listing_package_id",),
    "preflight_results": ("preflight_result_id",),
}
EXPECTED_INDEXES: dict[str, set[str]] = {table: set[str]() for table in EXPECTED_TABLES} | {
    "workflow_runs": {"workflow_runs_idempotency_key_key"},
    "jobs": {
        "jobs_idempotency_key_key",
        "ix_jobs_ready_queue",
        "ix_jobs_workflow_order",
    },
    "domain_events": {"ix_domain_events_workflow_order"},
    "artifacts": {"ix_artifacts_workflow_path", "uq_artifacts_workflow_path"},
}
EXPECTED_INDEX_DEFINITIONS: dict[str, dict[str, tuple[tuple[str, ...], bool]]] = {
    table: dict[str, tuple[tuple[str, ...], bool]]() for table in EXPECTED_TABLES
} | {
    "workflow_runs": {
        "workflow_runs_idempotency_key_key": (("idempotency_key",), True),
    },
    "jobs": {
        "jobs_idempotency_key_key": (("idempotency_key",), True),
        "ix_jobs_ready_queue": (("state", "available_at", "created_at", "job_id"), False),
        "ix_jobs_workflow_order": (("workflow_run_id", "created_at", "job_id"), False),
    },
    "domain_events": {
        "ix_domain_events_workflow_order": (
            ("workflow_run_id", "occurred_at", "event_id"),
            False,
        ),
    },
    "artifacts": {
        "ix_artifacts_workflow_path": (("workflow_run_id", "relative_path"), False),
        "uq_artifacts_workflow_path": (("workflow_run_id", "relative_path"), True),
    },
}
EXPECTED_FOREIGN_KEYS: dict[str, set[tuple[tuple[str, ...], str, tuple[str, ...]]]] = {
    table: set[tuple[tuple[str, ...], str, tuple[str, ...]]]() for table in EXPECTED_TABLES
} | {
    "jobs": {(("workflow_run_id",), "workflow_runs", ("workflow_run_id",))},
    "job_dependencies": {
        (("job_id",), "jobs", ("job_id",)),
        (("depends_on_job_id",), "jobs", ("job_id",)),
    },
    "job_attempts": {(("job_id",), "jobs", ("job_id",))},
    "domain_events": {
        (("workflow_run_id",), "workflow_runs", ("workflow_run_id",)),
        (("job_id",), "jobs", ("job_id",)),
    },
    "artifacts": {(("workflow_run_id",), "workflow_runs", ("workflow_run_id",))},
    "evidence_references": {(("packet_id",), "research_packets", ("packet_id",))},
    "research_observations": {(("packet_id",), "research_packets", ("packet_id",))},
    "candidates": {(("packet_id",), "research_packets", ("packet_id",))},
    "qualification_scores": {(("candidate_id",), "candidates", ("candidate_id",))},
    "candidate_shortlists": {(("packet_id",), "research_packets", ("packet_id",))},
    "dedupe_results": {(("product_spec_id",), "product_specs", ("product_spec_id",))},
    "build_results": {(("product_spec_id",), "product_specs", ("product_spec_id",))},
    "product_qa_results": {(("build_id",), "build_results", ("build_id",))},
    "listing_packages": {
        (("product_spec_id",), "product_specs", ("product_spec_id",)),
        (("build_id",), "build_results", ("build_id",)),
    },
    "preflight_results": {(("listing_package_id",), "listing_packages", ("listing_package_id",))},
}
EXPECTED_UNIQUE_CONSTRAINTS: dict[str, set[tuple[str, ...]]] = {
    table: set[tuple[str, ...]]() for table in EXPECTED_TABLES
} | {
    "workflow_runs": {("idempotency_key",)},
    "jobs": {("idempotency_key",)},
    "artifacts": {("workflow_run_id", "relative_path")},
}
_PAYLOAD_TABLES = {
    "evidence_references",
    "research_packets",
    "research_observations",
    "candidates",
    "qualification_scores",
    "candidate_shortlists",
    "product_specs",
    "dedupe_results",
    "build_results",
    "product_qa_results",
    "listing_packages",
    "preflight_results",
}
EXPECTED_CHECK_CONSTRAINTS: dict[str, set[str]] = {table: set[str]() for table in EXPECTED_TABLES}
for _table in _PAYLOAD_TABLES:
    EXPECTED_CHECK_CONSTRAINTS[_table] = {f"ck_{_table}_hash"}
EXPECTED_CHECK_CONSTRAINTS.update(
    {
        "workflow_runs": {"ck_workflow_runs_state", "ck_workflow_runs_hash"},
        "jobs": {
            "ck_jobs_state",
            "ck_jobs_attempt_count",
            "ck_jobs_max_attempts",
            "ck_jobs_input_hash",
            "ck_jobs_result_binding",
            "ck_jobs_result_hash",
            "ck_jobs_lease_expiry",
            "ck_jobs_lease_binding",
        },
        "job_dependencies": {"ck_job_dependencies_not_self"},
        "job_attempts": {"ck_job_attempts_number", "ck_job_attempts_state"},
        "domain_events": {"ck_domain_events_hash"},
        "artifacts": {"ck_artifacts_byte_count", "ck_artifacts_hash"},
        "qualification_scores": {
            "ck_qualification_scores_hash",
            "ck_qualification_scores_score",
        },
    }
)


def _normalize_default(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(str(value).split())
    return "{}" if normalized == "'{}'::jsonb" else normalized


def _column_signature(column: Any) -> tuple[str, str, bool, str | None]:
    return (
        column.name,
        str(column.type.compile(dialect=postgresql.dialect())),
        bool(column.nullable),
        _normalize_default(None if column.server_default is None else column.server_default.arg),
    )


EXPECTED_COLUMNS: dict[str, tuple[tuple[str, str, bool, str | None], ...]] = {
    table_name: tuple(_column_signature(column) for column in table.columns)
    for table_name, table in schema_metadata.tables.items()
}
EXPECTED_FOREIGN_KEY_ACTIONS: dict[
    str,
    set[tuple[tuple[str, ...], str, tuple[str, ...], str | None, str | None]],
] = {
    table_name: {
        (
            tuple(element.parent.name for element in constraint.elements),
            constraint.referred_table.name,
            tuple(element.column.name for element in constraint.elements),
            constraint.ondelete,
            constraint.onupdate,
        )
        for constraint in table.foreign_key_constraints
    }
    for table_name, table in schema_metadata.tables.items()
}
EXPECTED_CHECK_EXPRESSIONS: dict[str, dict[str, str]] = {
    table: dict[str, str]() for table in EXPECTED_TABLES
}
for _table in _PAYLOAD_TABLES:
    EXPECTED_CHECK_EXPRESSIONS[_table] = {f"ck_{_table}_hash": "char_length(payload_sha256) = 64"}
EXPECTED_CHECK_EXPRESSIONS.update(
    {
        "workflow_runs": {
            "ck_workflow_runs_hash": "char_length(payload_sha256) = 64",
            "ck_workflow_runs_state": (
                "state = ANY (ARRAY['RESEARCHED'::text, 'QUALIFIED'::text, "
                "'SPECIFIED'::text, 'DEDUPE_PASSED'::text, 'BUILT'::text, "
                "'QA_PASSED'::text, 'MERCHANDISED'::text, 'PREFLIGHT_PASSED'::text, "
                "'DRAFT_READY'::text, 'INSUFFICIENT_EVIDENCE'::text, "
                "'REJECTED'::text, 'FAILED'::text])"
            ),
        },
        "jobs": {
            "ck_jobs_attempt_count": "attempt_count >= 0",
            "ck_jobs_input_hash": "char_length(input_sha256) = 64",
            "ck_jobs_result_binding": (
                "result_type IS NULL AND result_id IS NULL AND result_sha256 IS NULL OR "
                "result_type IS NOT NULL AND result_id IS NOT NULL "
                "AND result_sha256 IS NOT NULL"
            ),
            "ck_jobs_result_hash": ("result_sha256 IS NULL OR char_length(result_sha256) = 64"),
            "ck_jobs_lease_binding": (
                "(state = ANY (ARRAY['LEASED'::text, 'RUNNING'::text])) "
                "AND lease_owner IS NOT NULL AND lease_token IS NOT NULL "
                "AND leased_at IS NOT NULL AND lease_expires_at IS NOT NULL OR "
                "(state <> ALL (ARRAY['LEASED'::text, 'RUNNING'::text])) "
                "AND lease_owner IS NULL AND lease_token IS NULL "
                "AND leased_at IS NULL AND lease_expires_at IS NULL"
            ),
            "ck_jobs_lease_expiry": (
                "lease_expires_at IS NULL OR leased_at IS NULL OR lease_expires_at > leased_at"
            ),
            "ck_jobs_max_attempts": "max_attempts >= 1 AND max_attempts <= 5",
            "ck_jobs_state": (
                "state = ANY (ARRAY['PENDING'::text, 'READY'::text, 'LEASED'::text, "
                "'RUNNING'::text, 'RETRY_WAIT'::text, 'SUCCEEDED'::text, "
                "'FAILED'::text, 'CANCELLED'::text])"
            ),
        },
        "job_dependencies": {"ck_job_dependencies_not_self": "job_id <> depends_on_job_id"},
        "job_attempts": {
            "ck_job_attempts_number": "attempt_number >= 1",
            "ck_job_attempts_state": (
                "state = ANY (ARRAY['PENDING'::text, 'READY'::text, 'LEASED'::text, "
                "'RUNNING'::text, 'RETRY_WAIT'::text, 'SUCCEEDED'::text, "
                "'FAILED'::text, 'CANCELLED'::text])"
            ),
        },
        "domain_events": {"ck_domain_events_hash": "char_length(payload_sha256) = 64"},
        "artifacts": {
            "ck_artifacts_byte_count": "byte_count >= 0",
            "ck_artifacts_hash": "char_length(sha256) = 64",
        },
        "qualification_scores": {
            "ck_qualification_scores_hash": "char_length(payload_sha256) = 64",
            "ck_qualification_scores_score": (
                "score_total >= 0::numeric AND score_total <= 40::numeric"
            ),
        },
    }
)
REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class SchemaSnapshot:
    tables: set[str]
    columns: dict[str, tuple[tuple[str, str, bool, str | None], ...]]
    indexes: dict[str, set[str]]
    index_definitions: dict[str, dict[str, tuple[tuple[str, ...], bool]]]
    primary_keys: dict[str, tuple[str, ...]]
    foreign_keys: dict[str, set[tuple[tuple[str, ...], str, tuple[str, ...]]]]
    foreign_key_actions: dict[
        str,
        set[tuple[tuple[str, ...], str, tuple[str, ...], str | None, str | None]],
    ]
    unique_constraints: dict[str, set[tuple[str, ...]]]
    check_constraints: dict[str, set[str]]
    check_expressions: dict[str, dict[str, str]]


def _database_url() -> str:
    return os.environ["MONEY_MACHINE_TEST_DATABASE_URL"]


def _alembic_config() -> Config:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", _database_url())
    return config


async def _schema_snapshot() -> SchemaSnapshot:
    engine = create_async_engine(_database_url())
    try:
        async with engine.connect() as connection:

            def inspect_schema(sync: Any) -> SchemaSnapshot:
                inspector = inspect(sync)
                tables = set(inspector.get_table_names())
                domain_tables = EXPECTED_TABLES & tables
                return SchemaSnapshot(
                    tables=tables,
                    columns={
                        table: tuple(
                            (
                                column["name"],
                                str(column["type"].compile(dialect=postgresql.dialect())),
                                bool(column["nullable"]),
                                _normalize_default(column["default"]),
                            )
                            for column in inspector.get_columns(table)
                        )
                        for table in domain_tables
                    },
                    indexes={
                        table: {index["name"] for index in inspector.get_indexes(table)}
                        for table in domain_tables
                    },
                    index_definitions={
                        table: {
                            index["name"]: (
                                tuple(index["column_names"]),
                                bool(index["unique"]),
                            )
                            for index in inspector.get_indexes(table)
                        }
                        for table in domain_tables
                    },
                    primary_keys={
                        table: tuple(inspector.get_pk_constraint(table)["constrained_columns"])
                        for table in domain_tables
                    },
                    foreign_keys={
                        table: {
                            (
                                tuple(foreign_key["constrained_columns"]),
                                foreign_key["referred_table"],
                                tuple(foreign_key["referred_columns"]),
                            )
                            for foreign_key in inspector.get_foreign_keys(table)
                        }
                        for table in domain_tables
                    },
                    foreign_key_actions={
                        table: {
                            (
                                tuple(foreign_key["constrained_columns"]),
                                foreign_key["referred_table"],
                                tuple(foreign_key["referred_columns"]),
                                foreign_key["options"].get("ondelete"),
                                foreign_key["options"].get("onupdate"),
                            )
                            for foreign_key in inspector.get_foreign_keys(table)
                        }
                        for table in domain_tables
                    },
                    unique_constraints={
                        table: {
                            tuple(constraint["column_names"])
                            for constraint in inspector.get_unique_constraints(table)
                        }
                        for table in domain_tables
                    },
                    check_constraints={
                        table: {
                            constraint["name"]
                            for constraint in inspector.get_check_constraints(table)
                        }
                        for table in domain_tables
                    },
                    check_expressions={
                        table: {
                            constraint["name"]: " ".join(constraint["sqltext"].split())
                            for constraint in inspector.get_check_constraints(table)
                        }
                        for table in domain_tables
                    },
                )

            return await connection.run_sync(inspect_schema)
    finally:
        await engine.dispose()


def test_migration_creates_exact_first_slice_schema_and_replays() -> None:
    config = _alembic_config()
    command.upgrade(config, "head")
    schema = asyncio.run(_schema_snapshot())
    assert schema.tables == EXPECTED_TABLES | {"alembic_version"}
    assert schema.columns == EXPECTED_COLUMNS
    assert schema.primary_keys == EXPECTED_PRIMARY_KEYS
    assert schema.indexes == EXPECTED_INDEXES
    assert schema.index_definitions == EXPECTED_INDEX_DEFINITIONS
    assert schema.foreign_keys == EXPECTED_FOREIGN_KEYS
    assert schema.foreign_key_actions == EXPECTED_FOREIGN_KEY_ACTIONS
    assert schema.unique_constraints == EXPECTED_UNIQUE_CONSTRAINTS
    assert schema.check_constraints == EXPECTED_CHECK_CONSTRAINTS
    assert schema.check_expressions == EXPECTED_CHECK_EXPRESSIONS
    assert {"result_type", "result_id", "result_sha256"} <= {
        column[0] for column in schema.columns["jobs"]
    }
    assert {"ck_jobs_result_binding", "ck_jobs_result_hash"} <= schema.check_constraints["jobs"]
    assert "ix_jobs_ready_queue" in schema.indexes["jobs"]
    assert "ix_domain_events_workflow_order" in schema.indexes["domain_events"]
    assert "ix_artifacts_workflow_path" in schema.indexes["artifacts"]
    assert (("workflow_run_id",), "workflow_runs", ("workflow_run_id",)) in schema.foreign_keys[
        "jobs"
    ]
    assert (("job_id",), "jobs", ("job_id",)) in schema.foreign_keys["job_attempts"]
    assert (("packet_id",), "research_packets", ("packet_id",)) in schema.foreign_keys[
        "research_observations"
    ]
    assert ("idempotency_key",) in schema.unique_constraints["workflow_runs"]
    assert ("idempotency_key",) in schema.unique_constraints["jobs"]
    assert ("workflow_run_id", "relative_path") in schema.unique_constraints["artifacts"]
    assert {
        "ck_jobs_state",
        "ck_jobs_attempt_count",
        "ck_jobs_max_attempts",
        "ck_jobs_input_hash",
        "ck_jobs_result_binding",
        "ck_jobs_result_hash",
        "ck_jobs_lease_expiry",
        "ck_jobs_lease_binding",
    } <= schema.check_constraints["jobs"]
    assert "ck_job_dependencies_not_self" in schema.check_constraints["job_dependencies"]
    assert "ck_job_attempts_state" in schema.check_constraints["job_attempts"]
    assert "ck_domain_events_hash" in schema.check_constraints["domain_events"]
    assert "ck_qualification_scores_score" in schema.check_constraints["qualification_scores"]

    command.upgrade(config, "head")
    assert asyncio.run(_schema_snapshot()) == schema

    command.downgrade(config, "base")
    assert asyncio.run(_schema_snapshot()).tables == {"alembic_version"}
    command.upgrade(config, "head")
    assert asyncio.run(_schema_snapshot()) == schema


def test_migration_backfills_exact_binding_for_populated_completed_jobs() -> None:
    config = _alembic_config()
    command.downgrade(config, "base")
    command.upgrade(config, "0001")

    async def seed() -> None:
        engine = create_async_engine(_database_url())
        try:
            async with engine.begin() as connection:
                await connection.execute(
                    text(
                        """
                        INSERT INTO workflow_runs (
                            workflow_run_id, workflow_type, packet_id, state,
                            idempotency_key, payload, payload_sha256, created_at, updated_at
                        ) VALUES (
                            CAST(:workflow_id AS uuid), 'FIRST_PRODUCT_VERTICAL_SLICE',
                            :packet_id, 'RESEARCHED', :workflow_key,
                            CAST(:workflow_payload AS jsonb), :hash, now(), now()
                        )
                        """
                    ),
                    {
                        "workflow_id": "00000000-0000-0000-0000-000000000901",
                        "packet_id": "RPK-legacy-binding",
                        "workflow_key": "workflow:RPK-legacy-binding",
                        "workflow_payload": json.dumps({"legacy": True}),
                        "hash": "a" * 64,
                    },
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO research_packets (
                            packet_id, payload, payload_sha256
                        ) VALUES (
                            :packet_id, CAST(:packet_payload AS jsonb), :result_hash
                        )
                        """
                    ),
                    {
                        "packet_id": "RPK-legacy-binding",
                        "packet_payload": json.dumps({"packet_id": "RPK-legacy-binding"}),
                        "result_hash": "b" * 64,
                    },
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO jobs (
                            job_id, workflow_run_id, job_type, state, idempotency_key,
                            input_sha256, retry_class, max_attempts, attempt_count, payload
                        ) VALUES (
                            CAST(:job_id AS uuid), CAST(:workflow_id AS uuid),
                            'ADMIT_RESEARCH_PACKET', 'SUCCEEDED', :job_key,
                            :input_hash, 'NEVER', 1, 1, CAST(:job_payload AS jsonb)
                        )
                        """
                    ),
                    {
                        "job_id": "00000000-0000-0000-0000-000000000902",
                        "workflow_id": "00000000-0000-0000-0000-000000000901",
                        "job_key": "job:legacy-binding",
                        "input_hash": "c" * 64,
                        "job_payload": json.dumps({"legacy": True}),
                    },
                )
                await connection.execute(
                    text(
                        """
                        INSERT INTO domain_events (
                            event_id, workflow_run_id, job_id, name, occurred_at,
                            payload, payload_sha256
                        ) VALUES (
                            CAST(:event_id AS uuid), CAST(:workflow_id AS uuid),
                            CAST(:job_id AS uuid), 'research_packet_admitted', now(),
                            CAST(:event_payload AS jsonb), :event_hash
                        )
                        """
                    ),
                    {
                        "event_id": "00000000-0000-0000-0000-000000000903",
                        "workflow_id": "00000000-0000-0000-0000-000000000901",
                        "job_id": "00000000-0000-0000-0000-000000000902",
                        "event_payload": json.dumps(
                            {
                                "event_id": "00000000-0000-0000-0000-000000000903",
                                "workflow_run_id": "00000000-0000-0000-0000-000000000901",
                                "job_id": "00000000-0000-0000-0000-000000000902",
                                "name": "research_packet_admitted",
                                "occurred_at": "2026-08-10T00:00:00Z",
                                "payload": {"packet_id": "RPK-legacy-binding"},
                                "payload_sha256": "d" * 64,
                            }
                        ),
                        "event_hash": "d" * 64,
                    },
                )
        finally:
            await engine.dispose()

    async def read_binding() -> tuple[str | None, str | None, str | None]:
        engine = create_async_engine(_database_url())
        try:
            async with engine.connect() as connection:
                row = (
                    await connection.execute(
                        text(
                            """
                            SELECT result_type, result_id, result_sha256
                            FROM jobs
                            WHERE job_id = CAST(:job_id AS uuid)
                            """
                        ),
                        {"job_id": "00000000-0000-0000-0000-000000000902"},
                    )
                ).one()
                return row.result_type, row.result_id, row.result_sha256
        finally:
            await engine.dispose()

    async def read_event() -> tuple[dict[str, Any], str]:
        engine = create_async_engine(_database_url())
        try:
            async with engine.connect() as connection:
                row = (
                    await connection.execute(
                        text(
                            """
                            SELECT payload, payload_sha256
                            FROM domain_events
                            WHERE event_id = CAST(:event_id AS uuid)
                            """
                        ),
                        {"event_id": "00000000-0000-0000-0000-000000000903"},
                    )
                ).one()
                return dict(row.payload), row.payload_sha256
        finally:
            await engine.dispose()

    asyncio.run(seed())
    command.upgrade(config, "head")
    assert asyncio.run(read_binding()) == (
        "research_packets",
        "RPK-legacy-binding",
        "b" * 64,
    )
    event_payload = {
        "packet_id": "RPK-legacy-binding",
        "result_type": "research_packets",
        "result_id": "RPK-legacy-binding",
        "result_sha256": "b" * 64,
    }
    event_hash = canonical_sha256(event_payload)
    event_envelope, normalized_event_hash = asyncio.run(read_event())
    assert event_envelope["payload"] == event_payload
    assert event_envelope["payload_sha256"] == event_hash
    assert normalized_event_hash == event_hash
    command.downgrade(config, "base")
