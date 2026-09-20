"""Create the canonical Money Machine schema.

The workbook's 33 logical entities plus the twelve tables the Session 02 corrective
addendum and its closure reviews required, so Session 01's contracts persist in full:
evidence citations, reconcilable external effects, QA and preflight verdicts pinned to what
they checked, dedupe comparisons, listing-version artifacts, artifact parentage, decision
evidence, and an advisory record of the configuration in force.

Generated from ``money_machine.persistence.tables`` and reviewed by hand. ``pgcrypto`` is
enabled so ``gen_random_uuid`` is available; the downgrade deliberately leaves the
extension in place because other schemas in the same database may rely on it. Alembic does
not autogenerate triggers, so the append-only guarantee on ``events`` and ``receipts`` is
installed explicitly.

Revision ID: 9f46f3152a68
Revises:
Created: 2026-09-07 07:06:12.412903+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from money_machine.persistence.tables import (
    drop_append_only_triggers,
    install_append_only_triggers,
)

revision: str = "9f46f3152a68"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Apply the revision."""
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.create_table(
        "agent_definitions",
        sa.Column("agent_id", sa.String(length=3), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("implementation_version", sa.Integer(), nullable=False),
        sa.Column("contract_version", sa.Integer(), nullable=False),
        sa.Column("default_side_effect_class", sa.String(length=64), nullable=False),
        sa.Column("default_retry_class", sa.String(length=64), nullable=False),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False),
        sa.Column("commissioning_state", sa.String(length=64), nullable=False),
        sa.Column(
            "commissioning_evidence",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "agent_id ~ '^A(0[1-9]|1[0-6])$'", name=op.f("ck_agent_definitions_agent_id_format")
        ),
        sa.CheckConstraint(
            "commissioning_state <> 'COMMISSIONED' OR jsonb_array_length(commissioning_evidence) > 0",
            name=op.f("ck_agent_definitions_commissioned_requires_evidence"),
        ),
        sa.CheckConstraint(
            "commissioning_state IN ('DESIGNED', 'IMPLEMENTED', 'TESTED', 'COMMISSIONED', 'SUSPENDED')",
            name=op.f("ck_agent_definitions_commissioning_state_taxonomy"),
        ),
        sa.CheckConstraint(
            "default_retry_class IN ('SAFE', 'IDEMPOTENT', 'RECONCILE_FIRST', 'MANUAL_RESUME', 'NEVER')",
            name=op.f("ck_agent_definitions_default_retry_class_taxonomy"),
        ),
        sa.CheckConstraint(
            "default_side_effect_class IN ('NONE', 'EXTERNAL_READ', 'EXTERNAL_WRITE', 'EXTERNAL_SPEND', 'EXTERNAL_MESSAGE')",
            name=op.f("ck_agent_definitions_default_side_effect_class_taxonomy"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(commissioning_evidence) = 'array'",
            name=op.f("ck_agent_definitions_commissioning_evidence_is_an_array"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_definitions")),
        sa.UniqueConstraint(
            "agent_id",
            "contract_version",
            name=op.f("uq_agent_definitions_agent_id_contract_version"),
        ),
        sa.UniqueConstraint(
            "id",
            "agent_id",
            "contract_version",
            name=op.f("uq_agent_definitions_id_agent_id_contract_version"),
        ),
    )
    op.create_table(
        "config_references",
        sa.Column("config_name", sa.String(length=100), nullable=False),
        sa.Column("source_path", sa.String(length=500), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("advisory_only", sa.Boolean(), nullable=False),
        sa.Column(
            "loaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "advisory_only = true", name=op.f("ck_config_references_never_authoritative")
        ),
        sa.CheckConstraint("length(sha256) = 64", name=op.f("ck_config_references_sha256_length")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_config_references")),
        sa.UniqueConstraint(
            "config_name", "sha256", name=op.f("uq_config_references_config_name_sha256")
        ),
    )
    op.create_table(
        "prompt_versions",
        sa.Column("prompt_reference", sa.String(length=200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("source_path", sa.String(length=500), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("length(sha256) = 64", name=op.f("ck_prompt_versions_sha256_length")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prompt_versions")),
        sa.UniqueConstraint(
            "id",
            "prompt_reference",
            "sha256",
            name=op.f("uq_prompt_versions_id_prompt_reference_sha256"),
        ),
        sa.UniqueConstraint(
            "prompt_reference", "version", name=op.f("uq_prompt_versions_prompt_reference_version")
        ),
        sa.UniqueConstraint("sha256", name=op.f("uq_prompt_versions_sha256")),
    )
    op.create_table(
        "shops",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("provider_shop_id", sa.String(length=200), nullable=True),
        sa.Column("connection_state", sa.String(length=64), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "connection_state IN ('UNCONNECTED', 'PENDING_HOLDER_ACTION', 'CONNECTED', 'REVOKED')",
            name=op.f("ck_shops_connection_state_taxonomy"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_shops")),
        sa.UniqueConstraint("name", name=op.f("uq_shops_name")),
        sa.UniqueConstraint("provider_shop_id", name=op.f("uq_shops_provider_shop_id")),
    )
    op.create_table(
        "integration_accounts",
        sa.Column("shop_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("capability_channel", sa.String(length=64), nullable=False),
        sa.Column("connection_state", sa.String(length=64), nullable=False),
        sa.Column("credential_present", sa.Boolean(), nullable=False),
        sa.Column("blocker_code", sa.String(length=64), nullable=True),
        sa.Column(
            "safe_detail",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "capability_channel IN ('DIRECT_API', 'COMPOSIO', 'BROWSER', 'INTERNAL_RENDERER', 'MANUAL_EXTERNAL_BLOCKER')",
            name=op.f("ck_integration_accounts_capability_channel_taxonomy"),
        ),
        sa.CheckConstraint(
            "connection_state IN ('UNCONNECTED', 'PENDING_HOLDER_ACTION', 'CONNECTED', 'REVOKED')",
            name=op.f("ck_integration_accounts_connection_state_taxonomy"),
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name=op.f("fk_integration_accounts_shop_id_shops"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_accounts")),
        sa.UniqueConstraint(
            "shop_id", "provider", name=op.f("uq_integration_accounts_shop_id_provider")
        ),
    )
    op.create_index(
        op.f("ix_integration_accounts_shop_id"), "integration_accounts", ["shop_id"], unique=False
    )
    op.create_table(
        "scheduled_triggers",
        sa.Column("shop_id", sa.UUID(), nullable=False),
        sa.Column("trigger_kind", sa.String(length=64), nullable=False),
        sa.Column("trigger_key", sa.String(length=200), nullable=False),
        sa.Column("cron_expression", sa.String(length=100), nullable=False),
        sa.Column("next_fire_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "trigger_kind IN ('WEEKLY_REVIEW', 'MONTHLY_DEEP_PASS', 'BUILD_SLOT')",
            name=op.f("ck_scheduled_triggers_trigger_kind_taxonomy"),
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name=op.f("fk_scheduled_triggers_shop_id_shops"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scheduled_triggers")),
        sa.UniqueConstraint("trigger_key", name=op.f("uq_scheduled_triggers_trigger_key")),
    )
    op.create_index(
        "ix_scheduled_triggers_due",
        "scheduled_triggers",
        ["next_fire_at"],
        unique=False,
        postgresql_where=sa.text("active"),
    )
    op.create_index(
        op.f("ix_scheduled_triggers_shop_id"), "scheduled_triggers", ["shop_id"], unique=False
    )
    op.create_table(
        "workflow_runs",
        sa.Column("shop_id", sa.UUID(), nullable=False),
        sa.Column("workflow_type", sa.String(length=100), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("product_state", sa.String(length=64), nullable=False),
        sa.Column("parent_workflow_id", sa.UUID(), nullable=True),
        sa.Column("parent_decision_id", sa.UUID(), nullable=True),
        sa.Column("batch_id", sa.UUID(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "product_state IN ('DISCOVERED', 'RESEARCHING', 'RESEARCH_COMPLETE', 'QUALIFYING', 'QUALIFIED', 'REJECTED', 'TEARDOWN_PENDING', 'TEARDOWN_COMPLETE', 'SPEC_READY', 'DEDUPE_CHECK', 'RECONCEPTING', 'BUILDING', 'BUILD_QA', 'BUILD_REPAIR', 'VARIANT_BUILD', 'VARIANT_QA', 'MERCHANDISING', 'ASSET_BUILD', 'ASSET_QA', 'DRAFTING', 'DRAFT_READY', 'PREFLIGHT', 'LISTING_REPAIR', 'READY_TO_PUBLISH', 'PUBLISHED', 'POST_PUBLISH_QA', 'INCIDENT_REPAIR', 'OBSERVING', 'MATURE', 'EVALUATING', 'REPAIRING', 'DEACTIVATING', 'DEACTIVATED', 'SUCCESSOR_SPEC')",
            name=op.f("ck_workflow_runs_product_state_taxonomy"),
        ),
        sa.CheckConstraint(
            "parent_workflow_id IS NULL OR parent_workflow_id <> id",
            name=op.f("ck_workflow_runs_successor_is_new_workflow"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_workflow_runs_parent_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name=op.f("fk_workflow_runs_shop_id_shops"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workflow_runs")),
    )
    op.create_index(op.f("ix_workflow_runs_batch_id"), "workflow_runs", ["batch_id"], unique=False)
    op.create_index(
        op.f("ix_workflow_runs_parent_workflow_id"),
        "workflow_runs",
        ["parent_workflow_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_workflow_runs_product_state"), "workflow_runs", ["product_state"], unique=False
    )
    op.create_index(op.f("ix_workflow_runs_shop_id"), "workflow_runs", ["shop_id"], unique=False)
    op.create_table(
        "jobs",
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("job_type", sa.String(length=100), nullable=False),
        sa.Column("object_type", sa.String(length=100), nullable=False),
        sa.Column("object_id", sa.UUID(), nullable=False),
        sa.Column("owner_agent_id", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column(
            "input",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "success_contract",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("side_effect_class", sa.String(length=64), nullable=False),
        sa.Column("retry_class", sa.String(length=64), nullable=False),
        sa.Column("allowed_mode", sa.String(length=64), nullable=False),
        sa.Column("lease_owner", sa.String(length=100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "allowed_mode IN ('simulation', 'draft', 'live')",
            name=op.f("ck_jobs_allowed_mode_taxonomy"),
        ),
        sa.CheckConstraint(
            "owner_agent_id ~ '^A(0[1-9]|1[0-6])$'", name=op.f("ck_jobs_agent_id_format")
        ),
        sa.CheckConstraint(
            "retry_class IN ('SAFE', 'IDEMPOTENT', 'RECONCILE_FIRST', 'MANUAL_RESUME', 'NEVER')",
            name=op.f("ck_jobs_retry_class_taxonomy"),
        ),
        sa.CheckConstraint(
            "side_effect_class IN ('NONE', 'EXTERNAL_READ', 'EXTERNAL_WRITE', 'EXTERNAL_SPEND', 'EXTERNAL_MESSAGE')",
            name=op.f("ck_jobs_side_effect_class_taxonomy"),
        ),
        sa.CheckConstraint(
            "status IN ('PENDING', 'BLOCKED', 'READY', 'RUNNING', 'SUCCEEDED', 'FAILED', 'TERMINAL_FAILURE', 'CANCELLED', 'UNCERTAIN_EXTERNAL_EFFECT')",
            name=op.f("ck_jobs_status_taxonomy"),
        ),
        sa.CheckConstraint("attempt <= max_attempts", name=op.f("ck_jobs_attempt_within_budget")),
        sa.CheckConstraint("max_attempts > 0", name=op.f("ck_jobs_positive_attempt_budget")),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_jobs_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jobs")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_jobs_idempotency_key")),
    )
    op.create_index(
        "ix_jobs_lease_expiry",
        "jobs",
        ["lease_expires_at"],
        unique=False,
        postgresql_where=sa.text("status = 'RUNNING'"),
    )
    op.create_index(
        "ix_jobs_ready_due",
        "jobs",
        ["scheduled_at"],
        unique=False,
        postgresql_where=sa.text("status = 'READY'"),
    )
    op.create_index("ix_jobs_workflow_status", "jobs", ["workflow_id", "status"], unique=False)
    op.create_table(
        "agent_runs",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("agent_definition_id", sa.UUID(), nullable=False),
        sa.Column("agent_id", sa.String(length=3), nullable=False),
        sa.Column("agent_definition_version", sa.Integer(), nullable=False),
        sa.Column("prompt_version_id", sa.UUID(), nullable=False),
        sa.Column("prompt_reference", sa.String(length=200), nullable=False),
        sa.Column("prompt_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column(
            "output",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "error",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "(status = 'SUCCESS' AND error IS NULL) OR (status <> 'SUCCESS' AND error IS NOT NULL)",
            name=op.f("ck_agent_runs_structured_error_required"),
        ),
        sa.CheckConstraint(
            "agent_id ~ '^A(0[1-9]|1[0-6])$'", name=op.f("ck_agent_runs_agent_id_format")
        ),
        sa.CheckConstraint(
            "error IS NULL OR (error ? 'code' AND error ? 'message')",
            name=op.f("ck_agent_runs_error_is_a_structured_contract_error"),
        ),
        sa.CheckConstraint(
            "status IN ('SUCCESS', 'FAILURE', 'BLOCKED', 'UNCERTAIN_EXTERNAL_EFFECT')",
            name=op.f("ck_agent_runs_status_taxonomy"),
        ),
        sa.CheckConstraint(
            "completed_at >= started_at", name=op.f("ck_agent_runs_run_ends_after_start")
        ),
        sa.CheckConstraint(
            "length(prompt_sha256) = 64", name=op.f("ck_agent_runs_prompt_sha256_length")
        ),
        sa.ForeignKeyConstraint(
            ["agent_definition_id", "agent_id", "agent_definition_version"],
            [
                "agent_definitions.id",
                "agent_definitions.agent_id",
                "agent_definitions.contract_version",
            ],
            name="agent_definition_identity",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_agent_runs_job_id_jobs"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["prompt_version_id", "prompt_reference", "prompt_sha256"],
            ["prompt_versions.id", "prompt_versions.prompt_reference", "prompt_versions.sha256"],
            name="prompt_version_identity",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_runs")),
    )
    op.create_index(
        op.f("ix_agent_runs_agent_definition_id"),
        "agent_runs",
        ["agent_definition_id"],
        unique=False,
    )
    op.create_index(op.f("ix_agent_runs_job_id"), "agent_runs", ["job_id"], unique=False)
    op.create_index(
        op.f("ix_agent_runs_prompt_version_id"), "agent_runs", ["prompt_version_id"], unique=False
    )
    op.create_table(
        "effect_attempts",
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("effect_state", sa.String(length=64), nullable=False),
        sa.Column("provider_object_id", sa.String(length=200), nullable=True),
        sa.Column("reconciliation_attempt", sa.Integer(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "(effect_state = 'CONFIRMED' AND provider_object_id IS NOT NULL) OR (effect_state = 'ABSENT' AND provider_object_id IS NULL) OR effect_state = 'UNKNOWN'",
            name=op.f("ck_effect_attempts_effect_state_evidence"),
        ),
        sa.CheckConstraint(
            "effect_state IN ('CONFIRMED', 'ABSENT', 'UNKNOWN')",
            name=op.f("ck_effect_attempts_effect_state_taxonomy"),
        ),
        sa.CheckConstraint(
            "reconciliation_attempt >= 0",
            name=op.f("ck_effect_attempts_nonnegative_reconciliation_attempt"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_effect_attempts_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_effect_attempts")),
        sa.UniqueConstraint(
            "idempotency_key",
            "reconciliation_attempt",
            name=op.f("uq_effect_attempts_idempotency_key_reconciliation_attempt"),
        ),
    )
    op.create_index(
        op.f("ix_effect_attempts_effect_state"), "effect_attempts", ["effect_state"], unique=False
    )
    op.create_index(op.f("ix_effect_attempts_job_id"), "effect_attempts", ["job_id"], unique=False)
    op.create_table(
        "events",
        sa.Column("event_name", sa.String(length=64), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=True),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("agent_run_id", sa.UUID(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("dedupe_key", sa.String(length=200), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "event_name IN ('ACCOUNT_CONNECTED', 'RESEARCH_COMPLETED', 'NICHE_SHORTLISTED', 'PRODUCT_QUALIFIED', 'PRODUCT_REJECTED', 'TEARDOWN_COMPLETED', 'PRODUCT_SPEC_CREATED', 'DEDUPE_PASSED', 'DEDUPE_FAILED', 'BUILD_COMPLETED', 'BUILD_QA_PASSED', 'BUILD_QA_FAILED', 'VARIANTS_COMPLETED', 'ASSETS_COMPLETED', 'DRAFT_CREATED', 'PREFLIGHT_PASSED', 'PREFLIGHT_FAILED', 'LISTING_PUBLISHED', 'POST_PUBLISH_VERIFIED', 'METRICS_CAPTURED', 'LISTING_MATURED', 'LISTING_HELD', 'LISTING_REPAIR_REQUESTED', 'LISTING_CULLED', 'WINNER_DETECTED', 'SUCCESSOR_CREATED', 'CUSTOMER_ISSUE_RECEIVED', 'BROKEN_LINK_DETECTED', 'REPAIR_COMPLETED', 'JOB_FAILED', 'JOB_STALLED', 'CREDENTIAL_REQUIRED', 'ENVIRONMENT_AUDITED', 'SHOP_BOOTSTRAPPED', 'NICHE_SELECTED', 'COMPETITOR_PURCHASED', 'VARIANT_LINKS_VERIFIED', 'SCREENSHOTS_CAPTURED', 'LISTING_COPY_COMPLETED', 'DELIVERY_FILES_COMPLETED', 'PRICING_COMPLETED', 'PROOF_FEEDBACK_CAPTURED', 'SCHEDULE_CONFIGURED', 'BUILD_SLOT_DEFERRED', 'MONTHLY_REVIEW_COMPLETED', 'SCALE_DECIDED', 'LISTING_CULL_REQUESTED', 'REPAIR_APPLIED')",
            name=op.f("ck_events_event_name_taxonomy"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_events_job_id_jobs"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_events_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_events_dedupe_key")),
    )
    op.create_index(op.f("ix_events_aggregate_id"), "events", ["aggregate_id"], unique=False)
    op.create_index(op.f("ix_events_event_name"), "events", ["event_name"], unique=False)
    op.create_index(op.f("ix_events_job_id"), "events", ["job_id"], unique=False)
    op.create_index(op.f("ix_events_workflow_id"), "events", ["workflow_id"], unique=False)
    op.create_table(
        "idempotency_records",
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("side_effect_class", sa.String(length=64), nullable=False),
        sa.Column(
            "reserved_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "side_effect_class IN ('NONE', 'EXTERNAL_READ', 'EXTERNAL_WRITE', 'EXTERNAL_SPEND', 'EXTERNAL_MESSAGE')",
            name=op.f("ck_idempotency_records_side_effect_class_taxonomy"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_idempotency_records_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_idempotency_records")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_idempotency_records_idempotency_key")),
    )
    op.create_index(
        op.f("ix_idempotency_records_job_id"), "idempotency_records", ["job_id"], unique=False
    )
    op.create_table(
        "job_dependencies",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("depends_on_job_id", sa.UUID(), nullable=False),
        sa.Column("satisfied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "job_id <> depends_on_job_id", name=op.f("ck_job_dependencies_no_self_dependency")
        ),
        sa.ForeignKeyConstraint(
            ["depends_on_job_id"],
            ["jobs.id"],
            name=op.f("fk_job_dependencies_depends_on_job_id_jobs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_job_dependencies_job_id_jobs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_dependencies")),
        sa.UniqueConstraint(
            "job_id", "depends_on_job_id", name=op.f("uq_job_dependencies_job_id_depends_on_job_id")
        ),
    )
    op.create_index(
        op.f("ix_job_dependencies_depends_on_job_id"),
        "job_dependencies",
        ["depends_on_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_job_dependencies_job_id"), "job_dependencies", ["job_id"], unique=False
    )
    op.create_table(
        "products",
        sa.Column("shop_id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("producing_job_id", sa.UUID(), nullable=False),
        sa.Column("identity", sa.String(length=200), nullable=False),
        sa.Column("base_category", sa.String(length=200), nullable=False),
        sa.Column("working_title", sa.String(length=500), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["producing_job_id"],
            ["jobs.id"],
            name=op.f("fk_products_producing_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name=op.f("fk_products_shop_id_shops"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_products_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
    )
    op.create_index(
        op.f("ix_products_producing_job_id"), "products", ["producing_job_id"], unique=False
    )
    op.create_index(op.f("ix_products_shop_id"), "products", ["shop_id"], unique=False)
    op.create_index(op.f("ix_products_workflow_id"), "products", ["workflow_id"], unique=False)
    op.create_table(
        "receipts",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=100), nullable=False),
        sa.Column("side_effect_class", sa.String(length=64), nullable=False),
        sa.Column("autonomy_mode", sa.String(length=64), nullable=False),
        sa.Column("effect_state", sa.String(length=64), nullable=False),
        sa.Column("provider_object_id", sa.String(length=200), nullable=True),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column(
            "safe_detail",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "autonomy_mode IN ('simulation', 'draft', 'live')",
            name=op.f("ck_receipts_autonomy_mode_taxonomy"),
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_receipts_currency_is_iso4217")),
        sa.CheckConstraint(
            "effect_state IN ('CONFIRMED', 'ABSENT', 'UNKNOWN')",
            name=op.f("ck_receipts_effect_state_taxonomy"),
        ),
        sa.CheckConstraint(
            "side_effect_class IN ('NONE', 'EXTERNAL_READ', 'EXTERNAL_WRITE', 'EXTERNAL_SPEND', 'EXTERNAL_MESSAGE')",
            name=op.f("ck_receipts_side_effect_class_taxonomy"),
        ),
        sa.CheckConstraint(
            "(amount IS NULL) = (currency IS NULL)",
            name=op.f("ck_receipts_amount_needs_a_currency"),
        ),
        sa.CheckConstraint(
            "amount IS NULL OR amount >= 0", name=op.f("ck_receipts_nonnegative_amount")
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_receipts_job_id_jobs"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_receipts")),
        sa.UniqueConstraint(
            "idempotency_key",
            "operation",
            "recorded_at",
            name=op.f("uq_receipts_idempotency_key_operation_recorded_at"),
        ),
    )
    op.create_index(op.f("ix_receipts_job_id"), "receipts", ["job_id"], unique=False)
    op.create_table(
        "research_runs",
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("source_policy_version", sa.String(length=64), nullable=False),
        sa.Column(
            "query_terms",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("observation_count", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "observation_count >= 0", name=op.f("ck_research_runs_nonnegative_observations")
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_research_runs_job_id_jobs"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_research_runs_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_runs")),
    )
    op.create_index(op.f("ix_research_runs_job_id"), "research_runs", ["job_id"], unique=False)
    op.create_index(
        op.f("ix_research_runs_workflow_id"), "research_runs", ["workflow_id"], unique=False
    )
    op.create_table(
        "artifacts",
        sa.Column("logical_role", sa.String(length=100), nullable=False),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("storage_reference", sa.String(length=500), nullable=False),
        sa.Column("producing_job_id", sa.UUID(), nullable=False),
        sa.Column("producing_agent_run_id", sa.UUID(), nullable=False),
        sa.Column("sensitivity", sa.String(length=64), nullable=False),
        sa.Column("retention_class", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "sensitivity IN ('PUBLIC', 'INTERNAL', 'DENIED')",
            name=op.f("ck_artifacts_sensitivity_taxonomy"),
        ),
        sa.CheckConstraint("byte_size >= 0", name=op.f("ck_artifacts_nonnegative_byte_size")),
        sa.CheckConstraint("length(sha256) = 64", name=op.f("ck_artifacts_sha256_length")),
        sa.ForeignKeyConstraint(
            ["producing_agent_run_id"],
            ["agent_runs.id"],
            name=op.f("fk_artifacts_producing_agent_run_id_agent_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["producing_job_id"],
            ["jobs.id"],
            name=op.f("fk_artifacts_producing_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifacts")),
        sa.UniqueConstraint(
            "sha256", "logical_role", name=op.f("uq_artifacts_sha256_logical_role")
        ),
    )
    op.create_index(
        op.f("ix_artifacts_producing_agent_run_id"),
        "artifacts",
        ["producing_agent_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_artifacts_producing_job_id"), "artifacts", ["producing_job_id"], unique=False
    )
    op.create_table(
        "etsy_listings",
        sa.Column("shop_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("provider_listing_id", sa.String(length=200), nullable=True),
        sa.Column("listing_state", sa.String(length=64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "listing_state IN ('DRAFT', 'ACTIVE', 'INACTIVE', 'EXPIRED')",
            name=op.f("ck_etsy_listings_listing_state_taxonomy"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_etsy_listings_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name=op.f("fk_etsy_listings_shop_id_shops"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_etsy_listings")),
        sa.UniqueConstraint(
            "provider_listing_id", name=op.f("uq_etsy_listings_provider_listing_id")
        ),
    )
    op.create_index(
        op.f("ix_etsy_listings_product_id"), "etsy_listings", ["product_id"], unique=False
    )
    op.create_index(op.f("ix_etsy_listings_shop_id"), "etsy_listings", ["shop_id"], unique=False)
    op.create_table(
        "experiments",
        sa.Column("shop_id", sa.UUID(), nullable=False),
        sa.Column("batch_id", sa.UUID(), nullable=False),
        sa.Column("hypothesis", sa.String(length=1000), nullable=False),
        sa.Column(
            "experiment_tags",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("concluded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "state IN ('QUEUED', 'RUNNING', 'CONCLUDED', 'ABANDONED')",
            name=op.f("ck_experiments_state_taxonomy"),
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_experiments_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name=op.f("fk_experiments_shop_id_shops"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_experiments")),
    )
    op.create_index(op.f("ix_experiments_batch_id"), "experiments", ["batch_id"], unique=False)
    op.create_index(op.f("ix_experiments_product_id"), "experiments", ["product_id"], unique=False)
    op.create_index(op.f("ix_experiments_shop_id"), "experiments", ["shop_id"], unique=False)
    op.create_table(
        "market_listing_observations",
        sa.Column("research_run_id", sa.UUID(), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("price", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("anchor_price", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("identity_niche", sa.String(length=200), nullable=True),
        sa.Column("base_category", sa.String(length=200), nullable=True),
        sa.Column(
            "facts",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'",
            name=op.f("ck_market_listing_observations_currency_is_iso4217"),
        ),
        sa.ForeignKeyConstraint(
            ["research_run_id"],
            ["research_runs.id"],
            name=op.f("fk_market_listing_observations_research_run_id_research_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_listing_observations")),
        sa.UniqueConstraint(
            "research_run_id",
            "source_reference",
            name=op.f("uq_market_listing_observations_research_run_id_source_reference"),
        ),
    )
    op.create_index(
        op.f("ix_market_listing_observations_research_run_id"),
        "market_listing_observations",
        ["research_run_id"],
        unique=False,
    )
    op.create_table(
        "market_shop_observations",
        sa.Column("research_run_id", sa.UUID(), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=False),
        sa.Column("shop_reference", sa.String(length=200), nullable=False),
        sa.Column("shop_sales", sa.Integer(), nullable=True),
        sa.Column("shop_opened_on", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "badges",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["research_run_id"],
            ["research_runs.id"],
            name=op.f("fk_market_shop_observations_research_run_id_research_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_market_shop_observations")),
        sa.UniqueConstraint(
            "research_run_id",
            "source_reference",
            name=op.f("uq_market_shop_observations_research_run_id_source_reference"),
        ),
    )
    op.create_index(
        op.f("ix_market_shop_observations_research_run_id"),
        "market_shop_observations",
        ["research_run_id"],
        unique=False,
    )
    op.create_table(
        "product_candidates",
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("research_run_id", sa.UUID(), nullable=False),
        sa.Column("identity", sa.String(length=200), nullable=False),
        sa.Column("base_category", sa.String(length=200), nullable=False),
        sa.Column("impulse_priced_score", sa.Integer(), nullable=True),
        sa.Column("tangible_score", sa.Integer(), nullable=True),
        sa.Column("honest_promise_score", sa.Integer(), nullable=True),
        sa.Column("trendy_but_tricky_score", sa.Integer(), nullable=True),
        sa.Column("total_score", sa.Integer(), nullable=True),
        sa.Column("maximum_score", sa.Integer(), nullable=True),
        sa.Column("selection", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "selection IN ('PRIMARY', 'BACKUP', 'REJECTED')",
            name=op.f("ck_product_candidates_selection_taxonomy"),
        ),
        sa.CheckConstraint(
            "total_score IS NULL OR maximum_score IS NULL OR total_score <= maximum_score",
            name=op.f("ck_product_candidates_score_within_maximum"),
        ),
        sa.ForeignKeyConstraint(
            ["research_run_id"],
            ["research_runs.id"],
            name=op.f("fk_product_candidates_research_run_id_research_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_product_candidates_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_candidates")),
        sa.UniqueConstraint(
            "workflow_id",
            "identity",
            "base_category",
            name=op.f("uq_product_candidates_workflow_id_identity_base_category"),
        ),
    )
    op.create_index(
        op.f("ix_product_candidates_research_run_id"),
        "product_candidates",
        ["research_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_candidates_workflow_id"),
        "product_candidates",
        ["workflow_id"],
        unique=False,
    )
    op.create_table(
        "artifact_lineage",
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("parent_artifact_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "artifact_id <> parent_artifact_id",
            name=op.f("ck_artifact_lineage_artifact_is_not_its_own_parent"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_artifact_lineage_artifact_id_artifacts"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["parent_artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_artifact_lineage_parent_artifact_id_artifacts"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_artifact_lineage")),
        sa.UniqueConstraint(
            "artifact_id",
            "parent_artifact_id",
            name=op.f("uq_artifact_lineage_artifact_id_parent_artifact_id"),
        ),
    )
    op.create_index(
        op.f("ix_artifact_lineage_artifact_id"), "artifact_lineage", ["artifact_id"], unique=False
    )
    op.create_index(
        op.f("ix_artifact_lineage_parent_artifact_id"),
        "artifact_lineage",
        ["parent_artifact_id"],
        unique=False,
    )
    op.create_table(
        "assets",
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("asset_role", sa.String(length=100), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("ordinal >= 0", name=op.f("ck_assets_nonnegative_ordinal")),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_assets_artifact_id_artifacts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_assets_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_assets")),
        sa.UniqueConstraint(
            "product_id",
            "asset_role",
            "ordinal",
            name=op.f("uq_assets_product_id_asset_role_ordinal"),
        ),
    )
    op.create_index(op.f("ix_assets_artifact_id"), "assets", ["artifact_id"], unique=False)
    op.create_index(op.f("ix_assets_product_id"), "assets", ["product_id"], unique=False)
    op.create_table(
        "competitor_purchases",
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("candidate_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("autonomy_mode", sa.String(length=64), nullable=False),
        sa.Column("effect_state", sa.String(length=64), nullable=False),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "autonomy_mode IN ('simulation', 'draft', 'live')",
            name=op.f("ck_competitor_purchases_autonomy_mode_taxonomy"),
        ),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'", name=op.f("ck_competitor_purchases_currency_is_iso4217")
        ),
        sa.CheckConstraint(
            "effect_state IN ('CONFIRMED', 'ABSENT', 'UNKNOWN')",
            name=op.f("ck_competitor_purchases_effect_state_taxonomy"),
        ),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_competitor_purchases_nonnegative_amount")),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["product_candidates.id"],
            name=op.f("fk_competitor_purchases_candidate_id_product_candidates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_competitor_purchases_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_competitor_purchases_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competitor_purchases")),
        sa.UniqueConstraint(
            "idempotency_key", name=op.f("uq_competitor_purchases_idempotency_key")
        ),
    )
    op.create_index(
        op.f("ix_competitor_purchases_candidate_id"),
        "competitor_purchases",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_competitor_purchases_job_id"), "competitor_purchases", ["job_id"], unique=False
    )
    op.create_index(
        op.f("ix_competitor_purchases_workflow_id"),
        "competitor_purchases",
        ["workflow_id"],
        unique=False,
    )
    op.create_table(
        "evidence_references",
        sa.Column("owner_type", sa.String(length=64), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("evidence_type", sa.String(length=100), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=False),
        sa.Column("safe_summary", sa.String(length=2000), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("artifact_id", sa.UUID(), nullable=True),
        sa.Column("producing_job_id", sa.UUID(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "owner_type IN ('research_runs', 'market_listing_observations', 'teardown_reports', 'product_specs', 'product_candidates', 'dedupe_results', 'dedupe_collisions', 'notion_builds', 'qa_results', 'listing_versions', 'preflight_results', 'metrics_snapshots', 'decisions', 'incidents', 'customer_issues', 'agent_runs', 'receipts')",
            name=op.f("ck_evidence_references_owner_type_taxonomy"),
        ),
        sa.CheckConstraint(
            "sha256 IS NULL OR length(sha256) = 64",
            name=op.f("ck_evidence_references_sha256_length"),
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_evidence_references_artifact_id_artifacts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["producing_job_id"],
            ["jobs.id"],
            name=op.f("fk_evidence_references_producing_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_references")),
        sa.UniqueConstraint(
            "owner_type",
            "owner_id",
            "source_reference",
            name=op.f("uq_evidence_references_owner_type_owner_id_source_reference"),
        ),
    )
    op.create_index(
        op.f("ix_evidence_references_artifact_id"),
        "evidence_references",
        ["artifact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evidence_references_owner_id"), "evidence_references", ["owner_id"], unique=False
    )
    op.create_index(
        op.f("ix_evidence_references_owner_type"),
        "evidence_references",
        ["owner_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_evidence_references_producing_job_id"),
        "evidence_references",
        ["producing_job_id"],
        unique=False,
    )
    op.create_table(
        "teardown_reports",
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("competitor_purchase_id", sa.UUID(), nullable=True),
        sa.Column("competitor_reference", sa.String(length=500), nullable=False),
        sa.Column(
            "structure_components",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "buyer_journey",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "mechanics",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("copied_protected_content", sa.Boolean(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "copied_protected_content = false",
            name=op.f("ck_teardown_reports_never_copy_protected_content"),
        ),
        sa.ForeignKeyConstraint(
            ["competitor_purchase_id"],
            ["competitor_purchases.id"],
            name=op.f("fk_teardown_reports_competitor_purchase_id_competitor_purchases"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_teardown_reports_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_teardown_reports")),
    )
    op.create_index(
        op.f("ix_teardown_reports_competitor_purchase_id"),
        "teardown_reports",
        ["competitor_purchase_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_teardown_reports_workflow_id"), "teardown_reports", ["workflow_id"], unique=False
    )
    op.create_table(
        "product_specs",
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("producing_job_id", sa.UUID(), nullable=False),
        sa.Column("producing_agent_run_id", sa.UUID(), nullable=False),
        sa.Column("research_run_id", sa.UUID(), nullable=True),
        sa.Column("teardown_report_id", sa.UUID(), nullable=True),
        sa.Column("lineage_kind", sa.String(length=64), nullable=False),
        sa.Column("parent_spec_id", sa.UUID(), nullable=True),
        sa.Column("parent_product_id", sa.UUID(), nullable=True),
        sa.Column("parent_decision_id", sa.UUID(), nullable=True),
        sa.Column("parent_workflow_id", sa.UUID(), nullable=True),
        sa.Column("identity", sa.String(length=200), nullable=False),
        sa.Column("base_category", sa.String(length=200), nullable=False),
        sa.Column("buyer_problem", sa.String(length=1000), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("tier", sa.String(length=64), nullable=False),
        sa.Column("real_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("anchor_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column(
            "hubs",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "colour_variants",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "features",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("experiment_plan", sa.String(length=1000), nullable=False),
        sa.Column("concept_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'", name=op.f("ck_product_specs_currency_is_iso4217")
        ),
        sa.CheckConstraint(
            "lineage_kind <> 'ORIGINAL' OR (parent_spec_id IS NULL AND parent_product_id IS NULL AND parent_decision_id IS NULL AND parent_workflow_id IS NULL)",
            name=op.f("ck_product_specs_original_has_no_parent_lineage"),
        ),
        sa.CheckConstraint(
            "lineage_kind <> 'RECONCEPT' OR parent_spec_id IS NOT NULL",
            name=op.f("ck_product_specs_reconcept_cites_its_parent_spec"),
        ),
        sa.CheckConstraint(
            "lineage_kind <> 'SUCCESSOR' OR (parent_workflow_id IS NOT NULL AND parent_workflow_id <> workflow_id)",
            name=op.f("ck_product_specs_successor_starts_a_new_workflow"),
        ),
        sa.CheckConstraint(
            "lineage_kind IN ('ORIGINAL', 'RECONCEPT', 'SUCCESSOR')",
            name=op.f("ck_product_specs_lineage_kind_taxonomy"),
        ),
        sa.CheckConstraint(
            "anchor_price >= real_price", name=op.f("ck_product_specs_anchor_at_least_real_price")
        ),
        sa.CheckConstraint(
            "length(concept_fingerprint) = 64", name=op.f("ck_product_specs_fingerprint_length")
        ),
        sa.CheckConstraint(
            "parent_spec_id IS NULL OR parent_spec_id <> id",
            name=op.f("ck_product_specs_spec_is_not_its_own_parent"),
        ),
        sa.ForeignKeyConstraint(
            ["parent_product_id"],
            ["products.id"],
            name=op.f("fk_product_specs_parent_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_spec_id"],
            ["product_specs.id"],
            name=op.f("fk_product_specs_parent_spec_id_product_specs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["parent_workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_product_specs_parent_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["producing_agent_run_id"],
            ["agent_runs.id"],
            name=op.f("fk_product_specs_producing_agent_run_id_agent_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["producing_job_id"],
            ["jobs.id"],
            name=op.f("fk_product_specs_producing_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_specs_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["research_run_id"],
            ["research_runs.id"],
            name=op.f("fk_product_specs_research_run_id_research_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["teardown_report_id"],
            ["teardown_reports.id"],
            name=op.f("fk_product_specs_teardown_report_id_teardown_reports"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_product_specs_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_specs")),
        sa.UniqueConstraint("id", "product_id", name=op.f("uq_product_specs_id_product_id")),
        sa.UniqueConstraint(
            "product_id", "version", name=op.f("uq_product_specs_product_id_version")
        ),
    )
    op.create_index(
        op.f("ix_product_specs_concept_fingerprint"),
        "product_specs",
        ["concept_fingerprint"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_specs_parent_product_id"),
        "product_specs",
        ["parent_product_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_specs_parent_spec_id"), "product_specs", ["parent_spec_id"], unique=False
    )
    op.create_index(
        op.f("ix_product_specs_parent_workflow_id"),
        "product_specs",
        ["parent_workflow_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_specs_producing_agent_run_id"),
        "product_specs",
        ["producing_agent_run_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_specs_producing_job_id"),
        "product_specs",
        ["producing_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_specs_product_id"), "product_specs", ["product_id"], unique=False
    )
    op.create_index(
        op.f("ix_product_specs_research_run_id"), "product_specs", ["research_run_id"], unique=False
    )
    op.create_index(
        op.f("ix_product_specs_teardown_report_id"),
        "product_specs",
        ["teardown_report_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_product_specs_workflow_id"), "product_specs", ["workflow_id"], unique=False
    )
    op.create_table(
        "decisions",
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("decision_type", sa.String(length=100), nullable=False),
        sa.Column("decision", sa.String(length=64), nullable=True),
        sa.Column("branch_outcome", sa.String(length=64), nullable=True),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("listing_id", sa.UUID(), nullable=True),
        sa.Column("cohort_reference", sa.String(length=200), nullable=True),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("explanation", sa.String(length=2000), nullable=False),
        sa.Column("successor_workflow_id", sa.UUID(), nullable=True),
        sa.Column("successor_spec_id", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "branch_outcome IN ('PASS', 'FAIL', 'TOO_CLOSE')",
            name=op.f("ck_decisions_branch_outcome_taxonomy"),
        ),
        sa.CheckConstraint(
            "coalesce(decision, '') <> 'MULTIPLY' OR (successor_workflow_id IS NOT NULL AND successor_workflow_id <> workflow_id AND successor_spec_id IS NOT NULL)",
            name=op.f("ck_decisions_multiply_creates_a_new_workflow"),
        ),
        sa.CheckConstraint(
            "coalesce(decision, '') = 'MULTIPLY' OR (successor_workflow_id IS NULL AND successor_spec_id IS NULL)",
            name=op.f("ck_decisions_only_multiply_has_a_successor"),
        ),
        sa.CheckConstraint(
            "decision IN ('HOLD', 'REPAIR', 'CULL', 'MULTIPLY')",
            name=op.f("ck_decisions_decision_taxonomy"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_decisions_job_id_jobs"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["etsy_listings.id"],
            name=op.f("fk_decisions_listing_id_etsy_listings"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_decisions_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["successor_spec_id"],
            ["product_specs.id"],
            name=op.f("fk_decisions_successor_spec_id_product_specs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["successor_workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_decisions_successor_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_decisions_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decisions")),
    )
    op.create_index(op.f("ix_decisions_job_id"), "decisions", ["job_id"], unique=False)
    op.create_index(op.f("ix_decisions_listing_id"), "decisions", ["listing_id"], unique=False)
    op.create_index(op.f("ix_decisions_product_id"), "decisions", ["product_id"], unique=False)
    op.create_index(
        op.f("ix_decisions_successor_spec_id"), "decisions", ["successor_spec_id"], unique=False
    )
    op.create_index(
        op.f("ix_decisions_successor_workflow_id"),
        "decisions",
        ["successor_workflow_id"],
        unique=False,
    )
    op.create_index(op.f("ix_decisions_workflow_id"), "decisions", ["workflow_id"], unique=False)
    op.create_table(
        "jev_evaluations",
        sa.Column("decision_id", sa.UUID(), nullable=True),
        sa.Column("decision_type", sa.String(length=100), nullable=False),
        sa.Column(
            "packet",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "answers",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "derived",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=True,
        ),
        sa.Column("model_id", sa.String(length=100), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint("latency_ms >= 0", name=op.f("ck_jev_evaluations_latency_non_negative")),
        sa.CheckConstraint(
            "jsonb_typeof(packet) = 'object'",
            name=op.f("ck_jev_evaluations_packet_is_object"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(answers) = 'object'",
            name=op.f("ck_jev_evaluations_answers_is_object"),
        ),
        sa.CheckConstraint(
            "derived IS NULL OR jsonb_typeof(derived) = 'object'",
            name=op.f("ck_jev_evaluations_derived_is_object_or_null"),
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["decisions.id"],
            name=op.f("fk_jev_evaluations_decision_id_decisions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_jev_evaluations")),
    )
    op.create_index(
        op.f("ix_jev_evaluations_decision_id"),
        "jev_evaluations",
        ["decision_id"],
        unique=False,
    )
    op.create_table(
        "dedupe_results",
        sa.Column("workflow_id", sa.UUID(), nullable=False),
        sa.Column("spec_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("normalized_title", sa.String(length=500), nullable=False),
        sa.Column("concept_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("title_similarity_threshold", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column(
            "differentiation_evidence",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "outcome <> 'TOO_CLOSE' OR jsonb_array_length(differentiation_evidence) = 0",
            name=op.f("ck_dedupe_results_too_close_claims_no_differentiation"),
        ),
        sa.CheckConstraint(
            "outcome IN ('PASS', 'TOO_CLOSE')", name=op.f("ck_dedupe_results_outcome_taxonomy")
        ),
        sa.CheckConstraint(
            "title_similarity_threshold > 0 AND title_similarity_threshold <= 1",
            name=op.f("ck_dedupe_results_threshold_is_a_unit_fraction"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_dedupe_results_job_id_jobs"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["spec_id"],
            ["product_specs.id"],
            name=op.f("fk_dedupe_results_spec_id_product_specs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_dedupe_results_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dedupe_results")),
        sa.UniqueConstraint(
            "spec_id", "rule_version", name=op.f("uq_dedupe_results_spec_id_rule_version")
        ),
    )
    op.create_index(op.f("ix_dedupe_results_job_id"), "dedupe_results", ["job_id"], unique=False)
    op.create_index(op.f("ix_dedupe_results_spec_id"), "dedupe_results", ["spec_id"], unique=False)
    op.create_index(
        op.f("ix_dedupe_results_workflow_id"), "dedupe_results", ["workflow_id"], unique=False
    )
    op.create_table(
        "product_facts",
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("spec_id", sa.UUID(), nullable=False),
        sa.Column("fact_key", sa.String(length=100), nullable=False),
        sa.Column(
            "fact_value",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verification_job_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_facts_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["spec_id"],
            ["product_specs.id"],
            name=op.f("fk_product_facts_spec_id_product_specs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["verification_job_id"],
            ["jobs.id"],
            name=op.f("fk_product_facts_verification_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_facts")),
        sa.UniqueConstraint(
            "product_id", "fact_key", name=op.f("uq_product_facts_product_id_fact_key")
        ),
    )
    op.create_index(
        op.f("ix_product_facts_product_id"), "product_facts", ["product_id"], unique=False
    )
    op.create_index(op.f("ix_product_facts_spec_id"), "product_facts", ["spec_id"], unique=False)
    op.create_index(
        op.f("ix_product_facts_verification_job_id"),
        "product_facts",
        ["verification_job_id"],
        unique=False,
    )
    op.create_table(
        "product_variants",
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("spec_id", sa.UUID(), nullable=False),
        sa.Column("variant_name", sa.String(length=100), nullable=False),
        sa.Column("build_version", sa.Integer(), nullable=False),
        sa.Column("duplicate_as_template_enabled", sa.Boolean(), nullable=False),
        sa.Column("search_indexing_disabled", sa.Boolean(), nullable=False),
        sa.Column("links_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_product_variants_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["spec_id"],
            ["product_specs.id"],
            name=op.f("fk_product_variants_spec_id_product_specs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_variants")),
        sa.UniqueConstraint(
            "product_id",
            "variant_name",
            "build_version",
            name=op.f("uq_product_variants_product_id_variant_name_build_version"),
        ),
    )
    op.create_index(
        op.f("ix_product_variants_product_id"), "product_variants", ["product_id"], unique=False
    )
    op.create_index(
        op.f("ix_product_variants_spec_id"), "product_variants", ["spec_id"], unique=False
    )
    op.create_table(
        "asset_links",
        sa.Column("asset_id", sa.UUID(), nullable=True),
        sa.Column("variant_id", sa.UUID(), nullable=True),
        sa.Column("link_role", sa.String(length=100), nullable=False),
        sa.Column("link_reference", sa.String(length=1000), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verification_result", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "verification_result IN ('VERIFIED', 'BROKEN', 'UNKNOWN')",
            name=op.f("ck_asset_links_verification_result_taxonomy"),
        ),
        sa.CheckConstraint(
            "(asset_id IS NOT NULL) <> (variant_id IS NOT NULL)",
            name=op.f("ck_asset_links_link_belongs_to_exactly_one_owner"),
        ),
        sa.ForeignKeyConstraint(
            ["asset_id"],
            ["assets.id"],
            name=op.f("fk_asset_links_asset_id_assets"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name=op.f("fk_asset_links_variant_id_product_variants"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_asset_links")),
    )
    op.create_index(op.f("ix_asset_links_asset_id"), "asset_links", ["asset_id"], unique=False)
    op.create_index(op.f("ix_asset_links_variant_id"), "asset_links", ["variant_id"], unique=False)
    op.create_table(
        "dedupe_collisions",
        sa.Column("dedupe_result_id", sa.UUID(), nullable=False),
        sa.Column("other_spec_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=64), nullable=False),
        sa.Column("similarity", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "reason IN ('EXACT_IDENTITY_CATEGORY', 'TITLE_SIMILARITY', 'CONCEPT_FINGERPRINT')",
            name=op.f("ck_dedupe_collisions_reason_taxonomy"),
        ),
        sa.CheckConstraint(
            "similarity >= 0 AND similarity <= 1",
            name=op.f("ck_dedupe_collisions_similarity_is_a_unit_fraction"),
        ),
        sa.ForeignKeyConstraint(
            ["dedupe_result_id"],
            ["dedupe_results.id"],
            name=op.f("fk_dedupe_collisions_dedupe_result_id_dedupe_results"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["other_spec_id"],
            ["product_specs.id"],
            name=op.f("fk_dedupe_collisions_other_spec_id_product_specs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dedupe_collisions")),
        sa.UniqueConstraint(
            "dedupe_result_id",
            "other_spec_id",
            "reason",
            name=op.f("uq_dedupe_collisions_dedupe_result_id_other_spec_id_reason"),
        ),
    )
    op.create_index(
        op.f("ix_dedupe_collisions_dedupe_result_id"),
        "dedupe_collisions",
        ["dedupe_result_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dedupe_collisions_other_spec_id"),
        "dedupe_collisions",
        ["other_spec_id"],
        unique=False,
    )
    op.create_table(
        "dedupe_comparisons",
        sa.Column("dedupe_result_id", sa.UUID(), nullable=False),
        sa.Column("compared_spec_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["compared_spec_id"],
            ["product_specs.id"],
            name=op.f("fk_dedupe_comparisons_compared_spec_id_product_specs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["dedupe_result_id"],
            ["dedupe_results.id"],
            name=op.f("fk_dedupe_comparisons_dedupe_result_id_dedupe_results"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_dedupe_comparisons")),
        sa.UniqueConstraint(
            "dedupe_result_id",
            "compared_spec_id",
            name=op.f("uq_dedupe_comparisons_dedupe_result_id_compared_spec_id"),
        ),
    )
    op.create_index(
        op.f("ix_dedupe_comparisons_compared_spec_id"),
        "dedupe_comparisons",
        ["compared_spec_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_dedupe_comparisons_dedupe_result_id"),
        "dedupe_comparisons",
        ["dedupe_result_id"],
        unique=False,
    )
    op.create_table(
        "notion_builds",
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("spec_id", sa.UUID(), nullable=False),
        sa.Column("variant_id", sa.UUID(), nullable=True),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("build_kind", sa.String(length=64), nullable=False),
        sa.Column("build_version", sa.Integer(), nullable=False),
        sa.Column(
            "checkpoint_names",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "provider_object_references",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "build_kind IN ('PRIMARY', 'VARIANT', 'REPAIR', 'ASSET', 'DELIVERY')",
            name=op.f("ck_notion_builds_build_kind_taxonomy"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_notion_builds_job_id_jobs"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_notion_builds_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["spec_id"],
            ["product_specs.id"],
            name=op.f("fk_notion_builds_spec_id_product_specs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["product_variants.id"],
            name=op.f("fk_notion_builds_variant_id_product_variants"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notion_builds")),
        sa.UniqueConstraint(
            "product_id",
            "build_kind",
            "build_version",
            "variant_id",
            name=op.f("uq_notion_builds_product_id_build_kind_build_version_variant_id"),
        ),
    )
    op.create_index(op.f("ix_notion_builds_job_id"), "notion_builds", ["job_id"], unique=False)
    op.create_index(
        op.f("ix_notion_builds_product_id"), "notion_builds", ["product_id"], unique=False
    )
    op.create_index(op.f("ix_notion_builds_spec_id"), "notion_builds", ["spec_id"], unique=False)
    op.create_index(
        op.f("ix_notion_builds_variant_id"), "notion_builds", ["variant_id"], unique=False
    )
    op.create_table(
        "qa_results",
        sa.Column("build_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column(
            "checks",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "defect_codes",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "(outcome = 'PASS' AND jsonb_array_length(defect_codes) = 0) OR (outcome = 'FAIL' AND jsonb_array_length(defect_codes) > 0)",
            name=op.f("ck_qa_results_defects_match_outcome"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(checks) = 'array'", name=op.f("ck_qa_results_checks_is_an_array")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(defect_codes) = 'array'",
            name=op.f("ck_qa_results_defect_codes_is_an_array"),
        ),
        sa.CheckConstraint(
            "outcome IN ('PASS', 'FAIL')", name=op.f("ck_qa_results_outcome_taxonomy")
        ),
        sa.ForeignKeyConstraint(
            ["build_id"],
            ["notion_builds.id"],
            name=op.f("fk_qa_results_build_id_notion_builds"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name=op.f("fk_qa_results_job_id_jobs"), ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_qa_results")),
    )
    op.create_index(op.f("ix_qa_results_build_id"), "qa_results", ["build_id"], unique=False)
    op.create_index(op.f("ix_qa_results_job_id"), "qa_results", ["job_id"], unique=False)
    op.create_table(
        "listing_versions",
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("spec_id", sa.UUID(), nullable=False),
        sa.Column("producing_job_id", sa.UUID(), nullable=False),
        sa.Column("qa_result_id", sa.UUID(), nullable=True),
        sa.Column("listing_version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column(
            "description_sections",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "tags",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("anchor_price", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("digital_product", sa.Boolean(), nullable=False),
        sa.Column("rule_version", sa.String(length=64), nullable=False),
        sa.Column("package_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'", name=op.f("ck_listing_versions_currency_is_iso4217")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(description_sections) = 'array'",
            name=op.f("ck_listing_versions_description_sections_is_an_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(tags) = 'array'", name=op.f("ck_listing_versions_tags_is_an_array")
        ),
        sa.CheckConstraint(
            "anchor_price >= price", name=op.f("ck_listing_versions_anchor_at_least_price")
        ),
        sa.CheckConstraint(
            "digital_product = true", name=op.f("ck_listing_versions_digital_delivery_only")
        ),
        sa.CheckConstraint(
            "length(package_sha256) = 64", name=op.f("ck_listing_versions_package_sha256_length")
        ),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_listing_versions_positive_quantity")),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["etsy_listings.id"],
            name=op.f("fk_listing_versions_listing_id_etsy_listings"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["producing_job_id"],
            ["jobs.id"],
            name=op.f("fk_listing_versions_producing_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            name=op.f("fk_listing_versions_product_id_products"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["qa_result_id"],
            ["qa_results.id"],
            name=op.f("fk_listing_versions_qa_result_id_qa_results"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["spec_id", "product_id"],
            ["product_specs.id", "product_specs.product_id"],
            name="spec_belongs_to_product",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listing_versions")),
        sa.UniqueConstraint(
            "id", "package_sha256", name=op.f("uq_listing_versions_id_package_sha256")
        ),
        sa.UniqueConstraint(
            "listing_id",
            "listing_version",
            name=op.f("uq_listing_versions_listing_id_listing_version"),
        ),
        sa.UniqueConstraint("package_sha256", name=op.f("uq_listing_versions_package_sha256")),
    )
    op.create_index(
        op.f("ix_listing_versions_listing_id"), "listing_versions", ["listing_id"], unique=False
    )
    op.create_index(
        op.f("ix_listing_versions_producing_job_id"),
        "listing_versions",
        ["producing_job_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_listing_versions_product_id"), "listing_versions", ["product_id"], unique=False
    )
    op.create_index(
        op.f("ix_listing_versions_qa_result_id"), "listing_versions", ["qa_result_id"], unique=False
    )
    op.create_index(
        op.f("ix_listing_versions_spec_id"), "listing_versions", ["spec_id"], unique=False
    )
    op.create_table(
        "qa_result_artifacts",
        sa.Column("qa_result_id", sa.UUID(), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_qa_result_artifacts_artifact_id_artifacts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["qa_result_id"],
            ["qa_results.id"],
            name=op.f("fk_qa_result_artifacts_qa_result_id_qa_results"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_qa_result_artifacts")),
        sa.UniqueConstraint(
            "qa_result_id",
            "artifact_id",
            name=op.f("uq_qa_result_artifacts_qa_result_id_artifact_id"),
        ),
    )
    op.create_index(
        op.f("ix_qa_result_artifacts_artifact_id"),
        "qa_result_artifacts",
        ["artifact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_qa_result_artifacts_qa_result_id"),
        "qa_result_artifacts",
        ["qa_result_id"],
        unique=False,
    )
    op.create_table(
        "incidents",
        sa.Column("shop_id", sa.UUID(), nullable=False),
        sa.Column("incident_type", sa.String(length=64), nullable=False),
        sa.Column("incident_state", sa.String(length=64), nullable=False),
        sa.Column("affected_object_type", sa.String(length=100), nullable=False),
        sa.Column("affected_object_id", sa.UUID(), nullable=False),
        sa.Column("workflow_id", sa.UUID(), nullable=True),
        sa.Column("listing_version_id", sa.UUID(), nullable=True),
        sa.Column("opened_by_job_id", sa.UUID(), nullable=False),
        sa.Column("resolved_by_job_id", sa.UUID(), nullable=True),
        sa.Column(
            "safe_detail",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "opened_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "(incident_state = 'RESOLVED') = (resolved_at IS NOT NULL)",
            name=op.f("ck_incidents_resolution_requires_a_time"),
        ),
        sa.CheckConstraint(
            "incident_state IN ('OPEN', 'REPAIRING', 'BLOCKED', 'RESOLVED', 'UNCERTAIN_EXTERNAL_EFFECT')",
            name=op.f("ck_incidents_incident_state_taxonomy"),
        ),
        sa.CheckConstraint(
            "incident_type IN ('BROKEN_LINK', 'CUSTOMER_ISSUE', 'BUILD_DEFECT', 'LISTING_DEFECT', 'CREDENTIAL_FAILURE', 'PROVIDER_MISMATCH', 'TERMINAL_JOB_FAILURE', 'UNCERTAIN_EXTERNAL_EFFECT')",
            name=op.f("ck_incidents_incident_type_taxonomy"),
        ),
        sa.ForeignKeyConstraint(
            ["listing_version_id"],
            ["listing_versions.id"],
            name=op.f("fk_incidents_listing_version_id_listing_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["opened_by_job_id"],
            ["jobs.id"],
            name=op.f("fk_incidents_opened_by_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_job_id"],
            ["jobs.id"],
            name=op.f("fk_incidents_resolved_by_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"], ["shops.id"], name=op.f("fk_incidents_shop_id_shops"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflow_runs.id"],
            name=op.f("fk_incidents_workflow_id_workflow_runs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incidents")),
    )
    op.create_index(
        op.f("ix_incidents_incident_state"), "incidents", ["incident_state"], unique=False
    )
    op.create_index(
        op.f("ix_incidents_incident_type"), "incidents", ["incident_type"], unique=False
    )
    op.create_index(
        op.f("ix_incidents_listing_version_id"), "incidents", ["listing_version_id"], unique=False
    )
    op.create_index(
        op.f("ix_incidents_opened_by_job_id"), "incidents", ["opened_by_job_id"], unique=False
    )
    op.create_index(
        op.f("ix_incidents_resolved_by_job_id"), "incidents", ["resolved_by_job_id"], unique=False
    )
    op.create_index(op.f("ix_incidents_shop_id"), "incidents", ["shop_id"], unique=False)
    op.create_index(op.f("ix_incidents_workflow_id"), "incidents", ["workflow_id"], unique=False)
    op.create_table(
        "listing_version_artifacts",
        sa.Column("listing_version_id", sa.UUID(), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "role IN ('listing_image', 'listing_video', 'delivery_pdf', 'free_gift_pdf')",
            name=op.f("ck_listing_version_artifacts_role_taxonomy"),
        ),
        sa.CheckConstraint(
            "ordinal >= 0", name=op.f("ck_listing_version_artifacts_nonnegative_ordinal")
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_listing_version_artifacts_artifact_id_artifacts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["listing_version_id"],
            ["listing_versions.id"],
            name=op.f("fk_listing_version_artifacts_listing_version_id_listing_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_listing_version_artifacts")),
        sa.UniqueConstraint(
            "listing_version_id",
            "artifact_id",
            name=op.f("uq_listing_version_artifacts_listing_version_id_artifact_id"),
        ),
        sa.UniqueConstraint(
            "listing_version_id",
            "role",
            "ordinal",
            name=op.f("uq_listing_version_artifacts_listing_version_id_role_ordinal"),
        ),
    )
    op.create_index(
        op.f("ix_listing_version_artifacts_artifact_id"),
        "listing_version_artifacts",
        ["artifact_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_listing_version_artifacts_listing_version_id"),
        "listing_version_artifacts",
        ["listing_version_id"],
        unique=False,
    )
    op.create_table(
        "metrics_snapshots",
        sa.Column("listing_id", sa.UUID(), nullable=False),
        sa.Column("listing_version_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("views", sa.Integer(), nullable=False),
        sa.Column("favourites", sa.Integer(), nullable=False),
        sa.Column("sales", sa.Integer(), nullable=False),
        sa.Column("revenue", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("live_days", sa.Integer(), nullable=False),
        sa.Column("reconciled", sa.Boolean(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'", name=op.f("ck_metrics_snapshots_currency_is_iso4217")
        ),
        sa.CheckConstraint(
            "views >= 0 AND favourites >= 0 AND sales >= 0 AND revenue >= 0 AND live_days >= 0",
            name=op.f("ck_metrics_snapshots_nonnegative_metrics"),
        ),
        sa.CheckConstraint(
            "window_end > window_start", name=op.f("ck_metrics_snapshots_window_is_ordered")
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_metrics_snapshots_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["etsy_listings.id"],
            name=op.f("fk_metrics_snapshots_listing_id_etsy_listings"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["listing_version_id"],
            ["listing_versions.id"],
            name=op.f("fk_metrics_snapshots_listing_version_id_listing_versions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_metrics_snapshots")),
        sa.UniqueConstraint(
            "listing_version_id",
            "window_start",
            "window_end",
            name=op.f("uq_metrics_snapshots_listing_version_id_window_start_window_end"),
        ),
    )
    op.create_index(
        op.f("ix_metrics_snapshots_job_id"), "metrics_snapshots", ["job_id"], unique=False
    )
    op.create_index(
        op.f("ix_metrics_snapshots_listing_id"), "metrics_snapshots", ["listing_id"], unique=False
    )
    op.create_index(
        op.f("ix_metrics_snapshots_listing_version_id"),
        "metrics_snapshots",
        ["listing_version_id"],
        unique=False,
    )
    op.create_table(
        "preflight_results",
        sa.Column("listing_version_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("outcome", sa.String(length=64), nullable=False),
        sa.Column("listing_package_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "checks",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column(
            "repair_job_types",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()).with_variant(
                sa.JSON(none_as_null=True), "sqlite"
            ),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "(outcome = 'PASS' AND jsonb_array_length(repair_job_types) = 0) OR (outcome = 'FAIL' AND jsonb_array_length(repair_job_types) > 0)",
            name=op.f("ck_preflight_results_repairs_match_outcome"),
        ),
        sa.CheckConstraint(
            "outcome IN ('PASS', 'FAIL')", name=op.f("ck_preflight_results_outcome_taxonomy")
        ),
        sa.CheckConstraint(
            "length(listing_package_sha256) = 64",
            name=op.f("ck_preflight_results_package_sha256_length"),
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["jobs.id"],
            name=op.f("fk_preflight_results_job_id_jobs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["listing_version_id", "listing_package_sha256"],
            ["listing_versions.id", "listing_versions.package_sha256"],
            name="listing_version_identity",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_preflight_results")),
    )
    op.create_index(
        op.f("ix_preflight_results_job_id"), "preflight_results", ["job_id"], unique=False
    )
    op.create_index(
        op.f("ix_preflight_results_listing_version_id"),
        "preflight_results",
        ["listing_version_id"],
        unique=False,
    )
    op.create_table(
        "customer_issues",
        sa.Column("shop_id", sa.UUID(), nullable=False),
        sa.Column("listing_id", sa.UUID(), nullable=True),
        sa.Column("incident_id", sa.UUID(), nullable=True),
        sa.Column("buyer_reference", sa.String(length=200), nullable=False),
        sa.Column("issue_state", sa.String(length=64), nullable=False),
        sa.Column("safe_summary", sa.String(length=2000), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.CheckConstraint(
            "issue_state IN ('RECEIVED', 'TRIAGED', 'ANSWERED', 'CLOSED')",
            name=op.f("ck_customer_issues_issue_state_taxonomy"),
        ),
        sa.ForeignKeyConstraint(
            ["incident_id"],
            ["incidents.id"],
            name=op.f("fk_customer_issues_incident_id_incidents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["etsy_listings.id"],
            name=op.f("fk_customer_issues_listing_id_etsy_listings"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shop_id"],
            ["shops.id"],
            name=op.f("fk_customer_issues_shop_id_shops"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_customer_issues")),
        sa.UniqueConstraint(
            "shop_id",
            "buyer_reference",
            "received_at",
            name=op.f("uq_customer_issues_shop_id_buyer_reference_received_at"),
        ),
    )
    op.create_index(
        op.f("ix_customer_issues_incident_id"), "customer_issues", ["incident_id"], unique=False
    )
    op.create_index(
        op.f("ix_customer_issues_listing_id"), "customer_issues", ["listing_id"], unique=False
    )
    op.create_index(
        op.f("ix_customer_issues_shop_id"), "customer_issues", ["shop_id"], unique=False
    )
    op.create_table(
        "decision_evidence",
        sa.Column("decision_id", sa.UUID(), nullable=False),
        sa.Column("evidence_type", sa.String(length=100), nullable=False),
        sa.Column("source_reference", sa.String(length=500), nullable=False),
        sa.Column("artifact_id", sa.UUID(), nullable=True),
        sa.Column("metrics_snapshot_id", sa.UUID(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name=op.f("fk_decision_evidence_artifact_id_artifacts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"],
            ["decisions.id"],
            name=op.f("fk_decision_evidence_decision_id_decisions"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["metrics_snapshot_id"],
            ["metrics_snapshots.id"],
            name=op.f("fk_decision_evidence_metrics_snapshot_id_metrics_snapshots"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_evidence")),
        sa.UniqueConstraint(
            "decision_id",
            "source_reference",
            name=op.f("uq_decision_evidence_decision_id_source_reference"),
        ),
    )
    op.create_index(
        op.f("ix_decision_evidence_artifact_id"), "decision_evidence", ["artifact_id"], unique=False
    )
    op.create_index(
        op.f("ix_decision_evidence_decision_id"), "decision_evidence", ["decision_id"], unique=False
    )
    op.create_index(
        op.f("ix_decision_evidence_metrics_snapshot_id"),
        "decision_evidence",
        ["metrics_snapshot_id"],
        unique=False,
    )

    install_append_only_triggers(op.execute)


def downgrade() -> None:
    """Reverse the revision."""
    drop_append_only_triggers(op.execute)
    op.drop_index(op.f("ix_decision_evidence_metrics_snapshot_id"), table_name="decision_evidence")
    op.drop_index(op.f("ix_decision_evidence_decision_id"), table_name="decision_evidence")
    op.drop_index(op.f("ix_decision_evidence_artifact_id"), table_name="decision_evidence")
    op.drop_table("decision_evidence")
    op.drop_index(op.f("ix_customer_issues_shop_id"), table_name="customer_issues")
    op.drop_index(op.f("ix_customer_issues_listing_id"), table_name="customer_issues")
    op.drop_index(op.f("ix_customer_issues_incident_id"), table_name="customer_issues")
    op.drop_table("customer_issues")
    op.drop_index(op.f("ix_preflight_results_listing_version_id"), table_name="preflight_results")
    op.drop_index(op.f("ix_preflight_results_job_id"), table_name="preflight_results")
    op.drop_table("preflight_results")
    op.drop_index(op.f("ix_metrics_snapshots_listing_version_id"), table_name="metrics_snapshots")
    op.drop_index(op.f("ix_metrics_snapshots_listing_id"), table_name="metrics_snapshots")
    op.drop_index(op.f("ix_metrics_snapshots_job_id"), table_name="metrics_snapshots")
    op.drop_table("metrics_snapshots")
    op.drop_index(
        op.f("ix_listing_version_artifacts_listing_version_id"),
        table_name="listing_version_artifacts",
    )
    op.drop_index(
        op.f("ix_listing_version_artifacts_artifact_id"), table_name="listing_version_artifacts"
    )
    op.drop_table("listing_version_artifacts")
    op.drop_index(op.f("ix_incidents_workflow_id"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_shop_id"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_resolved_by_job_id"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_opened_by_job_id"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_listing_version_id"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_incident_type"), table_name="incidents")
    op.drop_index(op.f("ix_incidents_incident_state"), table_name="incidents")
    op.drop_table("incidents")
    op.drop_index(op.f("ix_qa_result_artifacts_qa_result_id"), table_name="qa_result_artifacts")
    op.drop_index(op.f("ix_qa_result_artifacts_artifact_id"), table_name="qa_result_artifacts")
    op.drop_table("qa_result_artifacts")
    op.drop_index(op.f("ix_listing_versions_spec_id"), table_name="listing_versions")
    op.drop_index(op.f("ix_listing_versions_qa_result_id"), table_name="listing_versions")
    op.drop_index(op.f("ix_listing_versions_product_id"), table_name="listing_versions")
    op.drop_index(op.f("ix_listing_versions_producing_job_id"), table_name="listing_versions")
    op.drop_index(op.f("ix_listing_versions_listing_id"), table_name="listing_versions")
    op.drop_table("listing_versions")
    op.drop_index(op.f("ix_qa_results_job_id"), table_name="qa_results")
    op.drop_index(op.f("ix_qa_results_build_id"), table_name="qa_results")
    op.drop_table("qa_results")
    op.drop_index(op.f("ix_notion_builds_variant_id"), table_name="notion_builds")
    op.drop_index(op.f("ix_notion_builds_spec_id"), table_name="notion_builds")
    op.drop_index(op.f("ix_notion_builds_product_id"), table_name="notion_builds")
    op.drop_index(op.f("ix_notion_builds_job_id"), table_name="notion_builds")
    op.drop_table("notion_builds")
    op.drop_index(op.f("ix_dedupe_comparisons_dedupe_result_id"), table_name="dedupe_comparisons")
    op.drop_index(op.f("ix_dedupe_comparisons_compared_spec_id"), table_name="dedupe_comparisons")
    op.drop_table("dedupe_comparisons")
    op.drop_index(op.f("ix_dedupe_collisions_other_spec_id"), table_name="dedupe_collisions")
    op.drop_index(op.f("ix_dedupe_collisions_dedupe_result_id"), table_name="dedupe_collisions")
    op.drop_table("dedupe_collisions")
    op.drop_index(op.f("ix_asset_links_variant_id"), table_name="asset_links")
    op.drop_index(op.f("ix_asset_links_asset_id"), table_name="asset_links")
    op.drop_table("asset_links")
    op.drop_index(op.f("ix_product_variants_spec_id"), table_name="product_variants")
    op.drop_index(op.f("ix_product_variants_product_id"), table_name="product_variants")
    op.drop_table("product_variants")
    op.drop_index(op.f("ix_product_facts_verification_job_id"), table_name="product_facts")
    op.drop_index(op.f("ix_product_facts_spec_id"), table_name="product_facts")
    op.drop_index(op.f("ix_product_facts_product_id"), table_name="product_facts")
    op.drop_table("product_facts")
    op.drop_index(op.f("ix_dedupe_results_workflow_id"), table_name="dedupe_results")
    op.drop_index(op.f("ix_dedupe_results_spec_id"), table_name="dedupe_results")
    op.drop_index(op.f("ix_dedupe_results_job_id"), table_name="dedupe_results")
    op.drop_table("dedupe_results")
    op.drop_index(op.f("ix_decisions_workflow_id"), table_name="decisions")
    op.drop_index(op.f("ix_decisions_successor_workflow_id"), table_name="decisions")
    op.drop_index(op.f("ix_decisions_successor_spec_id"), table_name="decisions")
    op.drop_index(op.f("ix_decisions_product_id"), table_name="decisions")
    op.drop_index(op.f("ix_decisions_listing_id"), table_name="decisions")
    op.drop_index(op.f("ix_decisions_job_id"), table_name="decisions")
    op.drop_index(op.f("ix_jev_evaluations_decision_id"), table_name="jev_evaluations")
    op.drop_table("jev_evaluations")
    op.drop_table("decisions")
    op.drop_index(op.f("ix_product_specs_workflow_id"), table_name="product_specs")
    op.drop_index(op.f("ix_product_specs_teardown_report_id"), table_name="product_specs")
    op.drop_index(op.f("ix_product_specs_research_run_id"), table_name="product_specs")
    op.drop_index(op.f("ix_product_specs_product_id"), table_name="product_specs")
    op.drop_index(op.f("ix_product_specs_producing_job_id"), table_name="product_specs")
    op.drop_index(op.f("ix_product_specs_producing_agent_run_id"), table_name="product_specs")
    op.drop_index(op.f("ix_product_specs_parent_workflow_id"), table_name="product_specs")
    op.drop_index(op.f("ix_product_specs_parent_spec_id"), table_name="product_specs")
    op.drop_index(op.f("ix_product_specs_parent_product_id"), table_name="product_specs")
    op.drop_index(op.f("ix_product_specs_concept_fingerprint"), table_name="product_specs")
    op.drop_table("product_specs")
    op.drop_index(op.f("ix_teardown_reports_workflow_id"), table_name="teardown_reports")
    op.drop_index(op.f("ix_teardown_reports_competitor_purchase_id"), table_name="teardown_reports")
    op.drop_table("teardown_reports")
    op.drop_index(op.f("ix_evidence_references_producing_job_id"), table_name="evidence_references")
    op.drop_index(op.f("ix_evidence_references_owner_type"), table_name="evidence_references")
    op.drop_index(op.f("ix_evidence_references_owner_id"), table_name="evidence_references")
    op.drop_index(op.f("ix_evidence_references_artifact_id"), table_name="evidence_references")
    op.drop_table("evidence_references")
    op.drop_index(op.f("ix_competitor_purchases_workflow_id"), table_name="competitor_purchases")
    op.drop_index(op.f("ix_competitor_purchases_job_id"), table_name="competitor_purchases")
    op.drop_index(op.f("ix_competitor_purchases_candidate_id"), table_name="competitor_purchases")
    op.drop_table("competitor_purchases")
    op.drop_index(op.f("ix_assets_product_id"), table_name="assets")
    op.drop_index(op.f("ix_assets_artifact_id"), table_name="assets")
    op.drop_table("assets")
    op.drop_index(op.f("ix_artifact_lineage_parent_artifact_id"), table_name="artifact_lineage")
    op.drop_index(op.f("ix_artifact_lineage_artifact_id"), table_name="artifact_lineage")
    op.drop_table("artifact_lineage")
    op.drop_index(op.f("ix_product_candidates_workflow_id"), table_name="product_candidates")
    op.drop_index(op.f("ix_product_candidates_research_run_id"), table_name="product_candidates")
    op.drop_table("product_candidates")
    op.drop_index(
        op.f("ix_market_shop_observations_research_run_id"), table_name="market_shop_observations"
    )
    op.drop_table("market_shop_observations")
    op.drop_index(
        op.f("ix_market_listing_observations_research_run_id"),
        table_name="market_listing_observations",
    )
    op.drop_table("market_listing_observations")
    op.drop_index(op.f("ix_experiments_shop_id"), table_name="experiments")
    op.drop_index(op.f("ix_experiments_product_id"), table_name="experiments")
    op.drop_index(op.f("ix_experiments_batch_id"), table_name="experiments")
    op.drop_table("experiments")
    op.drop_index(op.f("ix_etsy_listings_shop_id"), table_name="etsy_listings")
    op.drop_index(op.f("ix_etsy_listings_product_id"), table_name="etsy_listings")
    op.drop_table("etsy_listings")
    op.drop_index(op.f("ix_artifacts_producing_job_id"), table_name="artifacts")
    op.drop_index(op.f("ix_artifacts_producing_agent_run_id"), table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index(op.f("ix_research_runs_workflow_id"), table_name="research_runs")
    op.drop_index(op.f("ix_research_runs_job_id"), table_name="research_runs")
    op.drop_table("research_runs")
    op.drop_index(op.f("ix_receipts_job_id"), table_name="receipts")
    op.drop_table("receipts")
    op.drop_index(op.f("ix_products_workflow_id"), table_name="products")
    op.drop_index(op.f("ix_products_shop_id"), table_name="products")
    op.drop_index(op.f("ix_products_producing_job_id"), table_name="products")
    op.drop_table("products")
    op.drop_index(op.f("ix_job_dependencies_job_id"), table_name="job_dependencies")
    op.drop_index(op.f("ix_job_dependencies_depends_on_job_id"), table_name="job_dependencies")
    op.drop_table("job_dependencies")
    op.drop_index(op.f("ix_idempotency_records_job_id"), table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index(op.f("ix_events_workflow_id"), table_name="events")
    op.drop_index(op.f("ix_events_job_id"), table_name="events")
    op.drop_index(op.f("ix_events_event_name"), table_name="events")
    op.drop_index(op.f("ix_events_aggregate_id"), table_name="events")
    op.drop_table("events")
    op.drop_index(op.f("ix_effect_attempts_job_id"), table_name="effect_attempts")
    op.drop_index(op.f("ix_effect_attempts_effect_state"), table_name="effect_attempts")
    op.drop_table("effect_attempts")
    op.drop_index(op.f("ix_agent_runs_prompt_version_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_job_id"), table_name="agent_runs")
    op.drop_index(op.f("ix_agent_runs_agent_definition_id"), table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_index("ix_jobs_workflow_status", table_name="jobs")
    op.drop_index(
        "ix_jobs_ready_due", table_name="jobs", postgresql_where=sa.text("status = 'READY'")
    )
    op.drop_index(
        "ix_jobs_lease_expiry", table_name="jobs", postgresql_where=sa.text("status = 'RUNNING'")
    )
    op.drop_table("jobs")
    op.drop_index(op.f("ix_workflow_runs_shop_id"), table_name="workflow_runs")
    op.drop_index(op.f("ix_workflow_runs_product_state"), table_name="workflow_runs")
    op.drop_index(op.f("ix_workflow_runs_parent_workflow_id"), table_name="workflow_runs")
    op.drop_index(op.f("ix_workflow_runs_batch_id"), table_name="workflow_runs")
    op.drop_table("workflow_runs")
    op.drop_index(op.f("ix_scheduled_triggers_shop_id"), table_name="scheduled_triggers")
    op.drop_index(
        "ix_scheduled_triggers_due",
        table_name="scheduled_triggers",
        postgresql_where=sa.text("active"),
    )
    op.drop_table("scheduled_triggers")
    op.drop_index(op.f("ix_integration_accounts_shop_id"), table_name="integration_accounts")
    op.drop_table("integration_accounts")
    op.drop_table("shops")
    op.drop_table("prompt_versions")
    op.drop_table("config_references")
    op.drop_table("agent_definitions")
