"""SQLAlchemy Core schema for the first-product vertical slice."""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    PrimaryKeyConstraint,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData()

PRODUCT_STATES = (
    "RESEARCHED",
    "QUALIFIED",
    "SPECIFIED",
    "DEDUPE_PASSED",
    "BUILT",
    "QA_PASSED",
    "MERCHANDISED",
    "PREFLIGHT_PASSED",
    "DRAFT_READY",
    "INSUFFICIENT_EVIDENCE",
    "REJECTED",
    "FAILED",
)
JOB_STATES = (
    "PENDING",
    "READY",
    "LEASED",
    "RUNNING",
    "RETRY_WAIT",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
)


def _in_check(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({quoted})"


workflow_runs = Table(
    "workflow_runs",
    metadata,
    Column("workflow_run_id", UUID(as_uuid=True), primary_key=True),
    Column("workflow_type", Text, nullable=False),
    Column("packet_id", Text, nullable=False),
    Column("state", Text, nullable=False),
    Column("idempotency_key", Text, nullable=False, unique=True),
    Column("payload", JSONB, nullable=False),
    Column("payload_sha256", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    CheckConstraint(_in_check("state", PRODUCT_STATES), name="ck_workflow_runs_state"),
    CheckConstraint("char_length(payload_sha256) = 64", name="ck_workflow_runs_hash"),
)

jobs = Table(
    "jobs",
    metadata,
    Column("job_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "workflow_run_id",
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.workflow_run_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("job_type", Text, nullable=False),
    Column("state", Text, nullable=False),
    Column("idempotency_key", Text, nullable=False, unique=True),
    Column("input_sha256", Text, nullable=False),
    Column("retry_class", Text, nullable=False),
    Column("max_attempts", Integer, nullable=False),
    Column("attempt_count", Integer, nullable=False, server_default="0"),
    Column("available_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("lease_owner", Text),
    Column("lease_token", Text),
    Column("leased_at", DateTime(timezone=True)),
    Column("lease_expires_at", DateTime(timezone=True)),
    Column("payload", JSONB, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint(_in_check("state", JOB_STATES), name="ck_jobs_state"),
    CheckConstraint("attempt_count >= 0", name="ck_jobs_attempt_count"),
    CheckConstraint("max_attempts BETWEEN 1 AND 5", name="ck_jobs_max_attempts"),
    CheckConstraint("char_length(input_sha256) = 64", name="ck_jobs_input_hash"),
    CheckConstraint(
        "lease_expires_at IS NULL OR leased_at IS NULL OR lease_expires_at > leased_at",
        name="ck_jobs_lease_expiry",
    ),
    CheckConstraint(
        "(state IN ('LEASED', 'RUNNING') AND lease_owner IS NOT NULL "
        "AND lease_token IS NOT NULL AND leased_at IS NOT NULL "
        "AND lease_expires_at IS NOT NULL) OR "
        "(state NOT IN ('LEASED', 'RUNNING') AND lease_owner IS NULL "
        "AND lease_token IS NULL AND leased_at IS NULL AND lease_expires_at IS NULL)",
        name="ck_jobs_lease_binding",
    ),
)
Index("ix_jobs_ready_queue", jobs.c.state, jobs.c.available_at, jobs.c.created_at, jobs.c.job_id)
Index("ix_jobs_workflow_order", jobs.c.workflow_run_id, jobs.c.created_at, jobs.c.job_id)

job_dependencies = Table(
    "job_dependencies",
    metadata,
    Column("job_id", UUID(as_uuid=True), ForeignKey("jobs.job_id", ondelete="CASCADE")),
    Column("depends_on_job_id", UUID(as_uuid=True), ForeignKey("jobs.job_id", ondelete="CASCADE")),
    PrimaryKeyConstraint("job_id", "depends_on_job_id"),
    CheckConstraint("job_id <> depends_on_job_id", name="ck_job_dependencies_not_self"),
)

job_attempts = Table(
    "job_attempts",
    metadata,
    Column("job_id", UUID(as_uuid=True), ForeignKey("jobs.job_id", ondelete="CASCADE")),
    Column("attempt_number", Integer, nullable=False),
    Column("state", Text, nullable=False),
    Column("lease_token", Text, nullable=False),
    Column("started_at", DateTime(timezone=True), nullable=False),
    Column("completed_at", DateTime(timezone=True)),
    Column("error_code", Text),
    Column("payload", JSONB, nullable=False, server_default="{}"),
    PrimaryKeyConstraint("job_id", "attempt_number"),
    CheckConstraint("attempt_number >= 1", name="ck_job_attempts_number"),
    CheckConstraint(_in_check("state", JOB_STATES), name="ck_job_attempts_state"),
)

domain_events = Table(
    "domain_events",
    metadata,
    Column("event_id", UUID(as_uuid=True), primary_key=True),
    Column(
        "workflow_run_id",
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.workflow_run_id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("job_id", UUID(as_uuid=True), ForeignKey("jobs.job_id", ondelete="SET NULL")),
    Column("name", Text, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("payload_sha256", Text, nullable=False),
    CheckConstraint("char_length(payload_sha256) = 64", name="ck_domain_events_hash"),
)
Index(
    "ix_domain_events_workflow_order",
    domain_events.c.workflow_run_id,
    domain_events.c.occurred_at,
    domain_events.c.event_id,
)

artifacts = Table(
    "artifacts",
    metadata,
    Column("artifact_id", Text, primary_key=True),
    Column("workflow_run_id", UUID(as_uuid=True), ForeignKey("workflow_runs.workflow_run_id")),
    Column("relative_path", Text, nullable=False),
    Column("media_type", Text, nullable=False),
    Column("byte_count", Integer, nullable=False),
    Column("sha256", Text, nullable=False),
    Column("payload", JSONB, nullable=False),
    UniqueConstraint("workflow_run_id", "relative_path", name="uq_artifacts_workflow_path"),
    CheckConstraint("byte_count >= 0", name="ck_artifacts_byte_count"),
    CheckConstraint("char_length(sha256) = 64", name="ck_artifacts_hash"),
)
Index("ix_artifacts_workflow_path", artifacts.c.workflow_run_id, artifacts.c.relative_path)


def _payload_table(
    name: str,
    identity: str,
    *,
    foreign_keys: tuple[tuple[str, str], ...] = (),
    score: bool = False,
) -> Table:
    columns: list[Column[Any]] = [Column(identity, Text, primary_key=True)]
    columns.extend(
        Column(column, Text, ForeignKey(target, ondelete="CASCADE"), nullable=False)
        for column, target in foreign_keys
    )
    if score:
        columns.append(Column("score_total", Numeric(5, 2), nullable=False))
    columns.extend(
        [
            Column("payload", JSONB, nullable=False),
            Column("payload_sha256", Text, nullable=False),
            Column(
                "created_at", DateTime(timezone=True), nullable=False, server_default=func.now()
            ),
        ]
    )
    constraints: list[CheckConstraint] = [
        CheckConstraint("char_length(payload_sha256) = 64", name=f"ck_{name}_hash")
    ]
    if score:
        constraints.append(CheckConstraint("score_total BETWEEN 0 AND 40", name=f"ck_{name}_score"))
    return Table(name, metadata, *columns, *constraints)


research_packets = _payload_table("research_packets", "packet_id")
evidence_references = _payload_table(
    "evidence_references",
    "evidence_id",
    foreign_keys=(("packet_id", "research_packets.packet_id"),),
)
research_observations = _payload_table(
    "research_observations",
    "observation_id",
    foreign_keys=(("packet_id", "research_packets.packet_id"),),
)
candidates = _payload_table(
    "candidates",
    "candidate_id",
    foreign_keys=(("packet_id", "research_packets.packet_id"),),
)
qualification_scores = _payload_table(
    "qualification_scores",
    "qualification_score_id",
    foreign_keys=(("candidate_id", "candidates.candidate_id"),),
    score=True,
)
candidate_shortlists = _payload_table(
    "candidate_shortlists",
    "shortlist_id",
    foreign_keys=(("packet_id", "research_packets.packet_id"),),
)
product_specs = _payload_table("product_specs", "product_spec_id")
dedupe_results = _payload_table(
    "dedupe_results",
    "dedupe_result_id",
    foreign_keys=(("product_spec_id", "product_specs.product_spec_id"),),
)
build_results = _payload_table(
    "build_results",
    "build_id",
    foreign_keys=(("product_spec_id", "product_specs.product_spec_id"),),
)
product_qa_results = _payload_table(
    "product_qa_results",
    "product_qa_result_id",
    foreign_keys=(("build_id", "build_results.build_id"),),
)
listing_packages = _payload_table(
    "listing_packages",
    "listing_package_id",
    foreign_keys=(
        ("product_spec_id", "product_specs.product_spec_id"),
        ("build_id", "build_results.build_id"),
    ),
)
preflight_results = _payload_table(
    "preflight_results",
    "preflight_result_id",
    foreign_keys=(("listing_package_id", "listing_packages.listing_package_id"),),
)
