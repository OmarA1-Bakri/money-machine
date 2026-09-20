"""Canonical PostgreSQL schema for the Money Machine modular monolith.

The workbook's logical model names 33 entities. The Session 02 corrective addendum makes
that list a minimum rather than a ceiling and adds four tables so Session 01's lineage
contracts have somewhere to live: ``effect_attempts`` (reconcilable external effects),
``qa_results``, ``preflight_results`` and ``dedupe_results``.

Conventions, from the workbook and ``docs/architecture/DATA_MODEL.md``:

* UUID primary keys;
* timezone-aware UTC timestamps, never naive;
* validated state strings rather than native database enums, so a taxonomy change is a
  constraint migration rather than a type rewrite;
* uniqueness wherever idempotency or immutability is claimed;
* partial indexes for the ready and due job queries the orchestrator will run;
* foreign keys for every lineage edge;
* soft deactivation for business records; events and receipts are append only.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any, Final
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from money_machine.domain.enums import (
    AgentRunStatus,
    AutonomyMode,
    BranchOutcome,
    CapabilityChannel,
    DecisionType,
    IncidentType,
    JobStatus,
    ProductLifecycleState,
    RetryClass,
    SideEffectClass,
)
from money_machine.domain.events import EventName

NAMING_CONVENTION: Final = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

JsonB = JSONB(none_as_null=True).with_variant(JSON(none_as_null=True), "sqlite")
"""JSONB on PostgreSQL; the JSON variant keeps the metadata inspectable offline.

``none_as_null`` matters: without it a Python ``None`` is stored as the JSON value ``null``,
which is not SQL ``NULL``, and every ``IS NULL`` constraint on a JSON column silently stops
working. The ``agent_runs`` structured-error constraint caught exactly that."""

CONNECTION_STATES: Final = ("UNCONNECTED", "PENDING_HOLDER_ACTION", "CONNECTED", "REVOKED")
"""Integration readiness. Never derived from a credential value (D-0016)."""

COMMISSIONING_STATES: Final = ("DESIGNED", "IMPLEMENTED", "TESTED", "COMMISSIONED", "SUSPENDED")
"""The real ladder from ``config/agents.yaml``; ``UNCOMMISSIONED`` is not a state."""

EFFECT_STATES: Final = ("CONFIRMED", "ABSENT", "UNKNOWN")
"""Reconciliation outcome for one attempted external effect (D-0025)."""

LINEAGE_KINDS: Final = ("ORIGINAL", "RECONCEPT", "SUCCESSOR")
BUILD_KINDS: Final = ("PRIMARY", "VARIANT", "REPAIR", "ASSET", "DELIVERY")
SENSITIVITIES: Final = ("PUBLIC", "INTERNAL", "DENIED")
DEDUPE_REASONS: Final = ("EXACT_IDENTITY_CATEGORY", "TITLE_SIMILARITY", "CONCEPT_FINGERPRINT")
DEDUPE_OUTCOMES: Final = ("PASS", "TOO_CLOSE")
"""``DedupeResult`` rejects ``FAIL`` in its own validator; the database says the same."""
QA_OUTCOMES: Final = ("PASS", "FAIL")
"""``ProductQAResult`` and ``PreflightResult`` reject ``TOO_CLOSE`` in their validators."""
INCIDENT_STATES: Final = ("OPEN", "REPAIRING", "BLOCKED", "RESOLVED", "UNCERTAIN_EXTERNAL_EFFECT")
"""Superset of ``IncidentResult.status``: the contract's four states plus ``REPAIRING`` for
work in flight. A test asserts the contract's values are a subset of this tuple."""
ISSUE_STATES: Final = ("RECEIVED", "TRIAGED", "ANSWERED", "CLOSED")
LISTING_STATES: Final = ("DRAFT", "ACTIVE", "INACTIVE", "EXPIRED")
TRIGGER_KINDS: Final = ("WEEKLY_REVIEW", "MONTHLY_DEEP_PASS", "BUILD_SLOT")
EVIDENCE_OWNERS: Final = (
    "research_runs",
    "market_listing_observations",
    "teardown_reports",
    "product_specs",
    "product_candidates",
    "dedupe_results",
    "dedupe_collisions",
    "notion_builds",
    "qa_results",
    "listing_versions",
    "preflight_results",
    "metrics_snapshots",
    "decisions",
    "incidents",
    "customer_issues",
    "agent_runs",
    "receipts",
)
"""Tables whose rows may cite evidence. Adding one means adding it here."""
LISTING_ARTIFACT_ROLES: Final = ("listing_image", "listing_video", "delivery_pdf", "free_gift_pdf")
"""Roles a listing-version artifact may hold; the counts live in ``config/product_rules.yaml``."""


WORKBOOK_ENTITIES: Final = (
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
)
"""The workbook's logical model, verbatim and in source order (section 11)."""

ADDENDUM_ENTITIES: Final = (
    "config_references",
    "evidence_references",
    "qa_result_artifacts",
    "dedupe_comparisons",
    "listing_version_artifacts",
    "effect_attempts",
    "qa_results",
    "preflight_results",
    "dedupe_results",
    "dedupe_collisions",
    "artifact_lineage",
    "decision_evidence",
)
"""Tables the Session 02 corrective addendum adds so Session 01's contracts persist.

``effect_attempts``, ``qa_results``, ``preflight_results`` and ``dedupe_results`` are named
by the addendum. ``dedupe_collisions``, ``artifact_lineage`` and ``decision_evidence``
normalise the repeating groups those contracts carry, rather than storing them as opaque
JSON that no constraint can police. ``config_references`` records which YAML file the
process loaded, by path and content hash, so a run is auditable without the database ever
becoming a second source of authority (addendum 3).
"""

EXPECTED_TABLES: Final = tuple(sorted((*WORKBOOK_ENTITIES, *ADDENDUM_ENTITIES)))
"""The exact table set the schema must define. A test asserts equality both ways."""


class Base(DeclarativeBase):
    """Declarative base carrying the deterministic constraint naming convention."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Identified(Base):
    """Every table is addressed by a UUID primary key.

    The key is generated in Python for ORM inserts and by the database for direct SQL, so
    neither path can produce a row without an identity.
    """

    __abstract__ = True

    id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=func.gen_random_uuid(),
    )


class Versioned(Identified):
    """A row whose concurrent edits are guarded by an integer version.

    ``version_id_col`` makes the guard real: SQLAlchemy adds ``WHERE version = :old`` to
    every UPDATE and raises ``StaleDataError`` when no row matches, so a second writer
    holding a stale copy loses instead of silently overwriting.
    """

    __abstract__ = True

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    @declared_attr.directive
    @classmethod
    def __mapper_args__(cls) -> dict[str, object]:
        return {"version_id_col": cls.__table__.c["version"]}


def _enum_values(enum_type: type[StrEnum]) -> tuple[str, ...]:
    """The exact string values of one domain taxonomy, in declaration order."""
    return tuple(member.value for member in enum_type)


def _check(name: str, values: tuple[str, ...]) -> CheckConstraint:
    rendered = ", ".join(f"'{value}'" for value in values)
    return CheckConstraint(f"{name} IN ({rendered})", name=f"{name}_taxonomy")


def state(
    name: str,
    values: tuple[str, ...],
    *,
    nullable: bool = False,
    default: str | None = None,
    index: bool = False,
) -> Mapped[Any]:
    """A validated state string constrained to exactly one taxonomy."""
    return mapped_column(
        name,
        String(64),
        _check(name, values),
        nullable=nullable,
        default=default,
        index=index,
    )


def ref(
    target: str,
    *,
    nullable: bool = False,
    index: bool = True,
    ondelete: str = "RESTRICT",
) -> Mapped[Any]:
    return mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        index=index,
    )


def moment(*, nullable: bool = False, default_now: bool = False) -> Mapped[Any]:
    return mapped_column(
        DateTime(timezone=True),
        nullable=nullable,
        server_default=func.now() if default_now else None,
    )


def text_column(*, nullable: bool = False, length: int | None = 200) -> Mapped[Any]:
    return mapped_column(String(length) if length else Text, nullable=nullable)


def money() -> Mapped[Any]:
    return mapped_column(Numeric(14, 2), nullable=False)


def currency(*, nullable: bool = False) -> Mapped[Any]:
    """An ISO 4217 alphabetic currency code."""
    return mapped_column(
        String(3),
        CheckConstraint("currency ~ '^[A-Z]{3}$'", name="currency_is_iso4217"),
        nullable=nullable,
    )


class ConfigReference(Identified):
    """An advisory record of one loaded configuration file.

    YAML remains the runtime authority (D-0019, D-0022, addendum 3). This table records
    only which file was loaded and its content hash, so a decision can be traced back to
    the configuration that was in force. Nothing reads these rows as a decision input, and
    no configuration *value* is stored here.
    """

    __tablename__ = "config_references"

    config_name: Mapped[str] = text_column(length=100)
    source_path: Mapped[str] = text_column(length=500)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    advisory_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    loaded_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("config_name", "sha256"),
        CheckConstraint("length(sha256) = 64", name="sha256_length"),
        CheckConstraint("advisory_only = true", name="never_authoritative"),
    )


class EvidenceReference(Identified):
    """One cited piece of durable evidence.

    Thirteen Session 01 contracts require at least one evidence citation. This is where
    those citations live: an opaque, safe reference plus optional links to the artifact or
    job that produced it. ``owner_type``/``owner_id`` are polymorphic because every result
    table cites evidence and a column per owner would be unusable; the pair is constrained
    to the tables that may cite.
    """

    __tablename__ = "evidence_references"

    owner_type: Mapped[str] = state("owner_type", EVIDENCE_OWNERS, index=True)
    owner_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    evidence_type: Mapped[str] = text_column(length=100)
    source_reference: Mapped[str] = text_column(length=500)
    safe_summary: Mapped[str] = text_column(length=2000)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    artifact_id: Mapped[UUID | None] = ref("artifacts.id", nullable=True)
    producing_job_id: Mapped[UUID | None] = ref("jobs.id", nullable=True)
    observed_at: Mapped[datetime] = moment()
    recorded_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("owner_type", "owner_id", "source_reference"),
        CheckConstraint("sha256 IS NULL OR length(sha256) = 64", name="sha256_length"),
    )


class QaResultArtifact(Identified):
    """The exact artifacts one QA verdict checked.

    A relation rather than a JSON list, so a verdict cannot name an artifact that does not
    exist (which a JSON array of identifiers cannot prevent).
    """

    __tablename__ = "qa_result_artifacts"

    qa_result_id: Mapped[UUID] = ref("qa_results.id", ondelete="CASCADE")
    artifact_id: Mapped[UUID] = ref("artifacts.id")

    __table_args__ = (UniqueConstraint("qa_result_id", "artifact_id"),)


class DedupeComparison(Identified):
    """One specification that a dedupe verdict actually compared against."""

    __tablename__ = "dedupe_comparisons"

    dedupe_result_id: Mapped[UUID] = ref("dedupe_results.id", ondelete="CASCADE")
    compared_spec_id: Mapped[UUID] = ref("product_specs.id")

    __table_args__ = (UniqueConstraint("dedupe_result_id", "compared_spec_id"),)


class ListingVersionArtifact(Identified):
    """One media or delivery artifact belonging to an immutable listing version."""

    __tablename__ = "listing_version_artifacts"

    listing_version_id: Mapped[UUID] = ref("listing_versions.id", ondelete="CASCADE")
    artifact_id: Mapped[UUID] = ref("artifacts.id")
    role: Mapped[str] = state("role", LISTING_ARTIFACT_ROLES)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("listing_version_id", "artifact_id"),
        UniqueConstraint("listing_version_id", "role", "ordinal"),
        CheckConstraint("ordinal >= 0", name="nonnegative_ordinal"),
    )


class Shop(Identified):
    """One Etsy shop, its readiness and its operating timezone."""

    __tablename__ = "shops"

    name: Mapped[str] = text_column()
    provider_shop_id: Mapped[str | None] = text_column(nullable=True)
    connection_state: Mapped[str] = state(
        "connection_state", CONNECTION_STATES, default="UNCONNECTED"
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = moment(default_now=True)
    deactivated_at: Mapped[datetime | None] = moment(nullable=True)

    __table_args__ = (
        UniqueConstraint("name"),
        UniqueConstraint("provider_shop_id"),
    )


class IntegrationAccount(Identified):
    """Provider readiness for one shop. Credential values are never stored here."""

    __tablename__ = "integration_accounts"

    shop_id: Mapped[UUID] = ref("shops.id")
    provider: Mapped[str] = text_column(length=64)
    capability_channel: Mapped[str] = state("capability_channel", _enum_values(CapabilityChannel))
    connection_state: Mapped[str] = state(
        "connection_state", CONNECTION_STATES, default="UNCONNECTED"
    )
    credential_present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    blocker_code: Mapped[str | None] = text_column(nullable=True, length=64)
    safe_detail: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False, default=dict)
    checked_at: Mapped[datetime | None] = moment(nullable=True)
    created_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (UniqueConstraint("shop_id", "provider"),)


class WorkflowRun(Versioned):
    """One durable product workflow. A MULTIPLY successor is always a new row (D-0017)."""

    __tablename__ = "workflow_runs"

    shop_id: Mapped[UUID] = ref("shops.id")
    workflow_type: Mapped[str] = text_column(length=100)
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    product_state: Mapped[str] = state(
        "product_state", _enum_values(ProductLifecycleState), default="DISCOVERED", index=True
    )
    parent_workflow_id: Mapped[UUID | None] = ref("workflow_runs.id", nullable=True)
    parent_decision_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    batch_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True, index=True)
    started_at: Mapped[datetime] = moment(default_now=True)
    completed_at: Mapped[datetime | None] = moment(nullable=True)

    __table_args__ = (
        CheckConstraint(
            "parent_workflow_id IS NULL OR parent_workflow_id <> id",
            name="successor_is_new_workflow",
        ),
    )


class Job(Versioned):
    """A durable unit of work carrying the full Session 09 job envelope."""

    __tablename__ = "jobs"

    workflow_id: Mapped[UUID] = ref("workflow_runs.id", index=False)
    job_type: Mapped[str] = text_column(length=100)
    object_type: Mapped[str] = text_column(length=100)
    object_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    owner_agent_id: Mapped[str] = mapped_column(
        String(3),
        CheckConstraint("owner_agent_id ~ '^A(0[1-9]|1[0-6])$'", name="agent_id_format"),
        nullable=False,
    )
    status: Mapped[str] = state("status", _enum_values(JobStatus), default="PENDING")
    input: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False, default=dict)
    success_contract: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False, default=dict)
    scheduled_at: Mapped[datetime] = moment()
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    idempotency_key: Mapped[str] = text_column(length=200)
    side_effect_class: Mapped[str] = state("side_effect_class", _enum_values(SideEffectClass))
    retry_class: Mapped[str] = state("retry_class", _enum_values(RetryClass))
    allowed_mode: Mapped[str] = state(
        "allowed_mode", _enum_values(AutonomyMode), default="simulation"
    )
    lease_owner: Mapped[str | None] = text_column(nullable=True, length=100)
    lease_expires_at: Mapped[datetime | None] = moment(nullable=True)
    heartbeat_at: Mapped[datetime | None] = moment(nullable=True)
    created_at: Mapped[datetime] = moment(default_now=True)
    updated_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        CheckConstraint("attempt <= max_attempts", name="attempt_within_budget"),
        CheckConstraint("max_attempts > 0", name="positive_attempt_budget"),
        Index("ix_jobs_ready_due", "scheduled_at", postgresql_where=(text("status = 'READY'"))),
        Index(
            "ix_jobs_lease_expiry",
            "lease_expires_at",
            postgresql_where=(text("status = 'RUNNING'")),
        ),
        Index("ix_jobs_workflow_status", "workflow_id", "status"),
    )


class JobDependency(Identified):
    """A predecessor that must succeed before a job becomes ready."""

    __tablename__ = "job_dependencies"

    job_id: Mapped[UUID] = ref("jobs.id", ondelete="CASCADE")
    depends_on_job_id: Mapped[UUID] = ref("jobs.id", ondelete="CASCADE")
    satisfied_at: Mapped[datetime | None] = moment(nullable=True)

    __table_args__ = (
        UniqueConstraint("job_id", "depends_on_job_id"),
        CheckConstraint("job_id <> depends_on_job_id", name="no_self_dependency"),
    )


class ScheduledTrigger(Identified):
    """A recurring trigger in UTC with a deterministic key, safe against duplicate firing."""

    __tablename__ = "scheduled_triggers"

    shop_id: Mapped[UUID] = ref("shops.id")
    trigger_kind: Mapped[str] = state("trigger_kind", TRIGGER_KINDS)
    trigger_key: Mapped[str] = text_column(length=200)
    cron_expression: Mapped[str] = text_column(length=100)
    next_fire_at: Mapped[datetime] = moment()
    last_fired_at: Mapped[datetime | None] = moment(nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("trigger_key"),
        Index("ix_scheduled_triggers_due", "next_fire_at", postgresql_where=(text("active"))),
    )


class Event(Identified):
    """Append-only durable domain event. Rows are immutable by database rule."""

    __tablename__ = "events"

    event_name: Mapped[str] = state("event_name", _enum_values(EventName), index=True)
    aggregate_type: Mapped[str] = text_column(length=100)
    aggregate_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    workflow_id: Mapped[UUID | None] = ref("workflow_runs.id", nullable=True)
    job_id: Mapped[UUID | None] = ref("jobs.id", nullable=True)
    agent_run_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False, default=dict)
    dedupe_key: Mapped[str] = text_column(length=200)
    occurred_at: Mapped[datetime] = moment()
    recorded_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (UniqueConstraint("dedupe_key"),)


class IdempotencyRecord(Identified):
    """The reservation that makes one external effect happen at most once."""

    __tablename__ = "idempotency_records"

    idempotency_key: Mapped[str] = text_column(length=200)
    job_id: Mapped[UUID] = ref("jobs.id")
    operation: Mapped[str] = text_column(length=100)
    side_effect_class: Mapped[str] = state("side_effect_class", _enum_values(SideEffectClass))
    reserved_at: Mapped[datetime] = moment(default_now=True)
    completed_at: Mapped[datetime | None] = moment(nullable=True)

    __table_args__ = (UniqueConstraint("idempotency_key"),)


class EffectAttempt(Identified):
    """One attempted external effect and its reconciliation outcome (D-0025).

    Added by the Session 02 corrective addendum. ``idempotency_records`` answers "may this
    effect run"; this table answers "what actually happened", which is what the
    ``UNCERTAIN_EXTERNAL_EFFECT`` path needs before it may retry.
    """

    __tablename__ = "effect_attempts"

    idempotency_key: Mapped[str] = text_column(length=200)
    job_id: Mapped[UUID] = ref("jobs.id")
    agent_run_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    provider: Mapped[str] = text_column(length=64)
    operation: Mapped[str] = text_column(length=100)
    effect_state: Mapped[str] = state("effect_state", EFFECT_STATES, index=True)
    provider_object_id: Mapped[str | None] = text_column(nullable=True)
    reconciliation_attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    observed_at: Mapped[datetime] = moment()
    recorded_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("idempotency_key", "reconciliation_attempt"),
        CheckConstraint(
            "(effect_state = 'CONFIRMED' AND provider_object_id IS NOT NULL)"
            " OR (effect_state = 'ABSENT' AND provider_object_id IS NULL)"
            " OR effect_state = 'UNKNOWN'",
            name="effect_state_evidence",
        ),
        CheckConstraint("reconciliation_attempt >= 0", name="nonnegative_reconciliation_attempt"),
    )


class AgentDefinition(Identified):
    """One A01-A16 agent contract and its commissioning state."""

    __tablename__ = "agent_definitions"

    agent_id: Mapped[str] = mapped_column(
        String(3),
        CheckConstraint("agent_id ~ '^A(0[1-9]|1[0-6])$'", name="agent_id_format"),
        nullable=False,
    )
    name: Mapped[str] = text_column()
    implementation_version: Mapped[int] = mapped_column(Integer, nullable=False)
    contract_version: Mapped[int] = mapped_column(Integer, nullable=False)
    default_side_effect_class: Mapped[str] = state(
        "default_side_effect_class", _enum_values(SideEffectClass)
    )
    default_retry_class: Mapped[str] = state("default_retry_class", _enum_values(RetryClass))
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    commissioning_state: Mapped[str] = state(
        "commissioning_state", COMMISSIONING_STATES, default="DESIGNED"
    )
    commissioning_evidence: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    created_at: Mapped[datetime] = moment(default_now=True)
    updated_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("agent_id", "contract_version"),
        # Target for the agent_runs composite foreign key.
        UniqueConstraint("id", "agent_id", "contract_version"),
        CheckConstraint(
            "commissioning_state <> 'COMMISSIONED'"
            " OR jsonb_array_length(commissioning_evidence) > 0",
            name="commissioned_requires_evidence",
        ),
        CheckConstraint(
            "jsonb_typeof(commissioning_evidence) = 'array'",
            name="commissioning_evidence_is_an_array",
        ),
    )


class PromptVersion(Identified):
    """An immutable, hashed prompt version. Nothing stores prompt text here."""

    __tablename__ = "prompt_versions"

    prompt_reference: Mapped[str] = text_column()
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_path: Mapped[str] = text_column(length=500)
    created_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("prompt_reference", "version"),
        UniqueConstraint("sha256"),
        # Target for the agent_runs composite foreign key.
        UniqueConstraint("id", "prompt_reference", "sha256"),
        CheckConstraint("length(sha256) = 64", name="sha256_length"),
    )


class AgentRun(Identified):
    """One agent execution, carrying the lineage chain the workbook requires (D-0025)."""

    __tablename__ = "agent_runs"

    job_id: Mapped[UUID] = ref("jobs.id")
    agent_definition_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False, index=True
    )
    agent_id: Mapped[str] = mapped_column(
        String(3),
        CheckConstraint("agent_id ~ '^A(0[1-9]|1[0-6])$'", name="agent_id_format"),
        nullable=False,
    )
    agent_definition_version: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_version_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False, index=True
    )
    prompt_reference: Mapped[str] = text_column()
    prompt_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = state("status", _enum_values(AgentRunStatus))
    output: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False, default=dict)
    error: Mapped[dict[str, Any] | None] = mapped_column(JsonB, nullable=True)
    started_at: Mapped[datetime] = moment()
    completed_at: Mapped[datetime] = moment()

    __table_args__ = (
        # Composite foreign keys, so the denormalised lineage cannot disagree with the rows
        # it cites: a run cannot claim an agent version or a prompt hash it did not use.
        ForeignKeyConstraint(
            ["agent_definition_id", "agent_id", "agent_definition_version"],
            [
                "agent_definitions.id",
                "agent_definitions.agent_id",
                "agent_definitions.contract_version",
            ],
            name="agent_definition_identity",
        ),
        ForeignKeyConstraint(
            ["prompt_version_id", "prompt_reference", "prompt_sha256"],
            [
                "prompt_versions.id",
                "prompt_versions.prompt_reference",
                "prompt_versions.sha256",
            ],
            name="prompt_version_identity",
        ),
        CheckConstraint("length(prompt_sha256) = 64", name="prompt_sha256_length"),
        CheckConstraint(
            "(status = 'SUCCESS' AND error IS NULL) OR (status <> 'SUCCESS' AND error IS NOT NULL)",
            name="structured_error_required",
        ),
        CheckConstraint(
            "error IS NULL OR (error ? 'code' AND error ? 'message')",
            name="error_is_a_structured_contract_error",
        ),
        CheckConstraint("completed_at >= started_at", name="run_ends_after_start"),
    )


class ResearchRun(Identified):
    """One market-research collection with its source policy and row count."""

    __tablename__ = "research_runs"

    workflow_id: Mapped[UUID] = ref("workflow_runs.id")
    job_id: Mapped[UUID] = ref("jobs.id")
    source_policy_version: Mapped[str] = text_column(length=64)
    query_terms: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime | None] = moment(nullable=True)
    created_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (CheckConstraint("observation_count >= 0", name="nonnegative_observations"),)


class MarketListingObservation(Identified):
    """One admitted competitor listing observation. Structure only, never copied content."""

    __tablename__ = "market_listing_observations"

    research_run_id: Mapped[UUID] = ref("research_runs.id", ondelete="CASCADE")
    source_reference: Mapped[str] = text_column(length=500)
    title: Mapped[str] = text_column(length=500)
    price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    anchor_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = currency(nullable=True)
    identity_niche: Mapped[str | None] = text_column(nullable=True)
    base_category: Mapped[str | None] = text_column(nullable=True)
    facts: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False, default=dict)
    observed_at: Mapped[datetime] = moment()

    __table_args__ = (UniqueConstraint("research_run_id", "source_reference"),)


class MarketShopObservation(Identified):
    """One admitted competitor shop observation, including young-and-fast signals."""

    __tablename__ = "market_shop_observations"

    research_run_id: Mapped[UUID] = ref("research_runs.id", ondelete="CASCADE")
    source_reference: Mapped[str] = text_column(length=500)
    shop_reference: Mapped[str] = text_column()
    shop_sales: Mapped[int | None] = mapped_column(Integer, nullable=True)
    shop_opened_on: Mapped[datetime | None] = moment(nullable=True)
    badges: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False, default=dict)
    observed_at: Mapped[datetime] = moment()

    __table_args__ = (UniqueConstraint("research_run_id", "source_reference"),)


class ProductCandidate(Identified):
    """A shortlisted identity-by-category candidate and its Low-Ticket score."""

    __tablename__ = "product_candidates"

    workflow_id: Mapped[UUID] = ref("workflow_runs.id")
    research_run_id: Mapped[UUID] = ref("research_runs.id")
    identity: Mapped[str] = text_column()
    base_category: Mapped[str] = text_column()
    impulse_priced_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tangible_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    honest_promise_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trendy_but_tricky_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maximum_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selection: Mapped[str | None] = state(
        "selection", ("PRIMARY", "BACKUP", "REJECTED"), nullable=True
    )
    created_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("workflow_id", "identity", "base_category"),
        CheckConstraint(
            "total_score IS NULL OR maximum_score IS NULL OR total_score <= maximum_score",
            name="score_within_maximum",
        ),
    )


class CompetitorPurchase(Identified):
    """A capped, reconciled competitor acquisition. Spend never happens without a receipt."""

    __tablename__ = "competitor_purchases"

    workflow_id: Mapped[UUID] = ref("workflow_runs.id")
    candidate_id: Mapped[UUID] = ref("product_candidates.id")
    job_id: Mapped[UUID] = ref("jobs.id")
    idempotency_key: Mapped[str] = text_column(length=200)
    amount: Mapped[Decimal] = money()
    currency: Mapped[str] = currency()
    autonomy_mode: Mapped[str] = state("autonomy_mode", _enum_values(AutonomyMode))
    effect_state: Mapped[str] = state("effect_state", EFFECT_STATES)
    purchased_at: Mapped[datetime | None] = moment(nullable=True)
    created_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        CheckConstraint("amount >= 0", name="nonnegative_amount"),
    )


class TeardownReport(Identified):
    """Structure-only teardown of a lawfully obtained competitor product."""

    __tablename__ = "teardown_reports"

    workflow_id: Mapped[UUID] = ref("workflow_runs.id")
    competitor_purchase_id: Mapped[UUID | None] = ref("competitor_purchases.id", nullable=True)
    competitor_reference: Mapped[str] = text_column(length=500)
    structure_components: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    buyer_journey: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    mechanics: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    copied_protected_content: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completed_at: Mapped[datetime] = moment()

    __table_args__ = (
        CheckConstraint("copied_protected_content = false", name="never_copy_protected_content"),
    )


class Product(Identified):
    """A product concept across its specification versions and variants."""

    __tablename__ = "products"

    shop_id: Mapped[UUID] = ref("shops.id")
    workflow_id: Mapped[UUID] = ref("workflow_runs.id")
    producing_job_id: Mapped[UUID] = ref("jobs.id")
    identity: Mapped[str] = text_column()
    base_category: Mapped[str] = text_column()
    working_title: Mapped[str] = text_column(length=500)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = moment(default_now=True)
    deactivated_at: Mapped[datetime | None] = moment(nullable=True)


class ProductSpec(Identified):
    """An immutable product specification version with explicit lineage (D-0017)."""

    __tablename__ = "product_specs"

    product_id: Mapped[UUID] = ref("products.id")
    workflow_id: Mapped[UUID] = ref("workflow_runs.id")
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    producing_job_id: Mapped[UUID] = ref("jobs.id")
    producing_agent_run_id: Mapped[UUID] = ref("agent_runs.id")
    research_run_id: Mapped[UUID | None] = ref("research_runs.id", nullable=True)
    teardown_report_id: Mapped[UUID | None] = ref("teardown_reports.id", nullable=True)
    lineage_kind: Mapped[str] = state("lineage_kind", LINEAGE_KINDS, default="ORIGINAL")
    parent_spec_id: Mapped[UUID | None] = ref("product_specs.id", nullable=True)
    parent_product_id: Mapped[UUID | None] = ref("products.id", nullable=True)
    parent_decision_id: Mapped[UUID | None] = mapped_column(PgUUID(as_uuid=True), nullable=True)
    parent_workflow_id: Mapped[UUID | None] = ref("workflow_runs.id", nullable=True)
    identity: Mapped[str] = text_column()
    base_category: Mapped[str] = text_column()
    buyer_problem: Mapped[str] = text_column(length=1000)
    title: Mapped[str] = text_column(length=500)
    tier: Mapped[str] = text_column(length=64)
    real_price: Mapped[Decimal] = money()
    anchor_price: Mapped[Decimal] = money()
    currency: Mapped[str] = currency()
    hubs: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    colour_variants: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    features: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    experiment_plan: Mapped[str] = text_column(length=1000)
    concept_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rule_version: Mapped[str] = text_column(length=64)
    created_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("product_id", "version"),
        # Target for the listing_versions composite foreign key.
        UniqueConstraint("id", "product_id"),
        CheckConstraint("anchor_price >= real_price", name="anchor_at_least_real_price"),
        CheckConstraint(
            "parent_spec_id IS NULL OR parent_spec_id <> id", name="spec_is_not_its_own_parent"
        ),
        CheckConstraint(
            "lineage_kind <> 'SUCCESSOR'"
            " OR (parent_workflow_id IS NOT NULL AND parent_workflow_id <> workflow_id)",
            name="successor_starts_a_new_workflow",
        ),
        CheckConstraint(
            "lineage_kind <> 'ORIGINAL' OR (parent_spec_id IS NULL AND parent_product_id IS NULL"
            " AND parent_decision_id IS NULL AND parent_workflow_id IS NULL)",
            name="original_has_no_parent_lineage",
        ),
        CheckConstraint(
            "lineage_kind <> 'RECONCEPT' OR parent_spec_id IS NOT NULL",
            name="reconcept_cites_its_parent_spec",
        ),
        CheckConstraint("length(concept_fingerprint) = 64", name="fingerprint_length"),
    )


class DedupeResult(Identified):
    """A dedupe verdict with its rule version and the catalogue it compared (D-0023)."""

    __tablename__ = "dedupe_results"

    workflow_id: Mapped[UUID] = ref("workflow_runs.id")
    spec_id: Mapped[UUID] = ref("product_specs.id")
    job_id: Mapped[UUID] = ref("jobs.id")
    outcome: Mapped[str] = state("outcome", DEDUPE_OUTCOMES)
    rule_version: Mapped[str] = text_column(length=64)
    normalized_title: Mapped[str] = text_column(length=500)
    concept_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    title_similarity_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    differentiation_evidence: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    completed_at: Mapped[datetime] = moment()

    __table_args__ = (
        UniqueConstraint("spec_id", "rule_version"),
        CheckConstraint(
            "title_similarity_threshold > 0 AND title_similarity_threshold <= 1",
            name="threshold_is_a_unit_fraction",
        ),
        CheckConstraint(
            "outcome <> 'TOO_CLOSE' OR jsonb_array_length(differentiation_evidence) = 0",
            name="too_close_claims_no_differentiation",
        ),
    )


class DedupeCollision(Identified):
    """One cited collision behind a TOO_CLOSE dedupe verdict."""

    __tablename__ = "dedupe_collisions"

    dedupe_result_id: Mapped[UUID] = ref("dedupe_results.id", ondelete="CASCADE")
    other_spec_id: Mapped[UUID] = ref("product_specs.id")
    reason: Mapped[str] = state("reason", DEDUPE_REASONS)
    similarity: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)

    __table_args__ = (
        UniqueConstraint("dedupe_result_id", "other_spec_id", "reason"),
        CheckConstraint(
            "similarity >= 0 AND similarity <= 1", name="similarity_is_a_unit_fraction"
        ),
    )


class ProductVariant(Identified):
    """One isolated colour or identity variant with its verified delivery link."""

    __tablename__ = "product_variants"

    product_id: Mapped[UUID] = ref("products.id")
    spec_id: Mapped[UUID] = ref("product_specs.id")
    variant_name: Mapped[str] = text_column(length=100)
    build_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    duplicate_as_template_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    search_indexing_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    links_verified_at: Mapped[datetime | None] = moment(nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = moment(default_now=True)
    deactivated_at: Mapped[datetime | None] = moment(nullable=True)

    __table_args__ = (UniqueConstraint("product_id", "variant_name", "build_version"),)


class NotionBuild(Identified):
    """A resumable provider build checkpoint set for one product or variant."""

    __tablename__ = "notion_builds"

    product_id: Mapped[UUID] = ref("products.id")
    spec_id: Mapped[UUID] = ref("product_specs.id")
    variant_id: Mapped[UUID | None] = ref("product_variants.id", nullable=True)
    job_id: Mapped[UUID] = ref("jobs.id")
    build_kind: Mapped[str] = state("build_kind", BUILD_KINDS)
    build_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    checkpoint_names: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    provider_object_references: Mapped[dict[str, Any]] = mapped_column(
        JsonB, nullable=False, default=dict
    )
    completed_at: Mapped[datetime | None] = moment(nullable=True)
    created_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (UniqueConstraint("product_id", "build_kind", "build_version", "variant_id"),)


class ProductFact(Identified):
    """A verified product fact. Listing claims may cite only these rows."""

    __tablename__ = "product_facts"

    product_id: Mapped[UUID] = ref("products.id")
    spec_id: Mapped[UUID] = ref("product_specs.id")
    fact_key: Mapped[str] = text_column(length=100)
    fact_value: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False)
    verified_at: Mapped[datetime] = moment()
    verification_job_id: Mapped[UUID] = ref("jobs.id")

    __table_args__ = (UniqueConstraint("product_id", "fact_key"),)


class Artifact(Identified):
    """Immutable produced bytes with provenance, sensitivity and retention."""

    __tablename__ = "artifacts"

    logical_role: Mapped[str] = text_column(length=100)
    media_type: Mapped[str] = text_column(length=100)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    storage_reference: Mapped[str] = text_column(length=500)
    producing_job_id: Mapped[UUID] = ref("jobs.id")
    producing_agent_run_id: Mapped[UUID] = ref("agent_runs.id")
    sensitivity: Mapped[str] = state("sensitivity", SENSITIVITIES, default="INTERNAL")
    retention_class: Mapped[str] = text_column(length=64)
    created_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("sha256", "logical_role"),
        CheckConstraint("length(sha256) = 64", name="sha256_length"),
        CheckConstraint("byte_size >= 0", name="nonnegative_byte_size"),
    )


class ArtifactLineage(Identified):
    """A parent-to-child artifact edge, so a derived asset names its source."""

    __tablename__ = "artifact_lineage"

    artifact_id: Mapped[UUID] = ref("artifacts.id", ondelete="CASCADE")
    parent_artifact_id: Mapped[UUID] = ref("artifacts.id")

    __table_args__ = (
        UniqueConstraint("artifact_id", "parent_artifact_id"),
        CheckConstraint("artifact_id <> parent_artifact_id", name="artifact_is_not_its_own_parent"),
    )


class Asset(Identified):
    """A listing image, video, or delivery document produced for one product."""

    __tablename__ = "assets"

    product_id: Mapped[UUID] = ref("products.id")
    artifact_id: Mapped[UUID] = ref("artifacts.id")
    asset_role: Mapped[str] = text_column(length=100)
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("product_id", "asset_role", "ordinal"),
        CheckConstraint("ordinal >= 0", name="nonnegative_ordinal"),
    )


class AssetLink(Identified):
    """A delivery or variant link and its last verification result."""

    __tablename__ = "asset_links"

    asset_id: Mapped[UUID | None] = ref("assets.id", nullable=True)
    variant_id: Mapped[UUID | None] = ref("product_variants.id", nullable=True)
    link_role: Mapped[str] = text_column(length=100)
    link_reference: Mapped[str] = text_column(length=1000)
    verified_at: Mapped[datetime | None] = moment(nullable=True)
    verification_result: Mapped[str | None] = state(
        "verification_result", ("VERIFIED", "BROKEN", "UNKNOWN"), nullable=True
    )
    created_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        CheckConstraint(
            "(asset_id IS NOT NULL) <> (variant_id IS NOT NULL)",
            name="link_belongs_to_exactly_one_owner",
        ),
    )


class QaResult(Identified):
    """A QA verdict naming the exact artifacts it checked (D-0025)."""

    __tablename__ = "qa_results"

    build_id: Mapped[UUID] = ref("notion_builds.id")
    job_id: Mapped[UUID] = ref("jobs.id")
    outcome: Mapped[str] = state("outcome", QA_OUTCOMES)
    checks: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    defect_codes: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    completed_at: Mapped[datetime] = moment()

    __table_args__ = (
        CheckConstraint("jsonb_typeof(checks) = 'array'", name="checks_is_an_array"),
        CheckConstraint(
            "jsonb_typeof(defect_codes) = 'array'",
            name="defect_codes_is_an_array",
        ),
        CheckConstraint(
            "(outcome = 'PASS' AND jsonb_array_length(defect_codes) = 0)"
            " OR (outcome = 'FAIL' AND jsonb_array_length(defect_codes) > 0)",
            name="defects_match_outcome",
        ),
    )


class EtsyListing(Identified):
    """One marketplace listing across its immutable versions."""

    __tablename__ = "etsy_listings"

    shop_id: Mapped[UUID] = ref("shops.id")
    product_id: Mapped[UUID] = ref("products.id")
    provider_listing_id: Mapped[str | None] = text_column(nullable=True)
    listing_state: Mapped[str] = state("listing_state", LISTING_STATES, default="DRAFT")
    published_at: Mapped[datetime | None] = moment(nullable=True)
    deactivated_at: Mapped[datetime | None] = moment(nullable=True)
    created_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (UniqueConstraint("provider_listing_id"),)


class ListingVersion(Identified):
    """An immutable listing package version, hashed so preflight can pin it."""

    __tablename__ = "listing_versions"

    listing_id: Mapped[UUID] = ref("etsy_listings.id")
    product_id: Mapped[UUID] = ref("products.id")
    spec_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    producing_job_id: Mapped[UUID] = ref("jobs.id")
    qa_result_id: Mapped[UUID | None] = ref("qa_results.id", nullable=True)
    listing_version: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = text_column(length=200)
    description_sections: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    tags: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    currency: Mapped[str] = currency()
    price: Mapped[Decimal] = money()
    anchor_price: Mapped[Decimal] = money()
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    digital_product: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rule_version: Mapped[str] = text_column(length=64)
    package_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("listing_id", "listing_version"),
        UniqueConstraint("package_sha256"),
        # Target for the preflight_results composite foreign key.
        UniqueConstraint("id", "package_sha256"),
        ForeignKeyConstraint(
            ["spec_id", "product_id"],
            ["product_specs.id", "product_specs.product_id"],
            name="spec_belongs_to_product",
        ),
        CheckConstraint("anchor_price >= price", name="anchor_at_least_price"),
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("digital_product = true", name="digital_delivery_only"),
        CheckConstraint("length(package_sha256) = 64", name="package_sha256_length"),
        CheckConstraint("jsonb_typeof(tags) = 'array'", name="tags_is_an_array"),
        CheckConstraint(
            "jsonb_typeof(description_sections) = 'array'",
            name="description_sections_is_an_array",
        ),
    )


class PreflightResult(Identified):
    """A launch-readiness verdict pinned to the exact listing package hash (D-0025)."""

    __tablename__ = "preflight_results"

    listing_version_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True), nullable=False, index=True
    )
    job_id: Mapped[UUID] = ref("jobs.id")
    outcome: Mapped[str] = state("outcome", QA_OUTCOMES)
    listing_package_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    checks: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    repair_job_types: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    completed_at: Mapped[datetime] = moment()

    __table_args__ = (
        # Composite foreign key: a preflight verdict cannot pin a hash the listing version
        # does not actually have, so a stale verdict is impossible rather than merely
        # discouraged (D-0025).
        ForeignKeyConstraint(
            ["listing_version_id", "listing_package_sha256"],
            ["listing_versions.id", "listing_versions.package_sha256"],
            name="listing_version_identity",
        ),
        CheckConstraint("length(listing_package_sha256) = 64", name="package_sha256_length"),
        CheckConstraint(
            "(outcome = 'PASS' AND jsonb_array_length(repair_job_types) = 0)"
            " OR (outcome = 'FAIL' AND jsonb_array_length(repair_job_types) > 0)",
            name="repairs_match_outcome",
        ),
    )


class MetricsSnapshot(Identified):
    """One weekly reconciled scorecard for a listing version."""

    __tablename__ = "metrics_snapshots"

    listing_id: Mapped[UUID] = ref("etsy_listings.id")
    listing_version_id: Mapped[UUID] = ref("listing_versions.id")
    job_id: Mapped[UUID] = ref("jobs.id")
    window_start: Mapped[datetime] = moment()
    window_end: Mapped[datetime] = moment()
    views: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    favourites: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sales: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revenue: Mapped[Decimal] = money()
    currency: Mapped[str] = currency()
    live_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reconciled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    captured_at: Mapped[datetime] = moment()

    __table_args__ = (
        UniqueConstraint("listing_version_id", "window_start", "window_end"),
        CheckConstraint("window_end > window_start", name="window_is_ordered"),
        CheckConstraint(
            "views >= 0 AND favourites >= 0 AND sales >= 0 AND revenue >= 0 AND live_days >= 0",
            name="nonnegative_metrics",
        ),
    )


class Experiment(Identified):
    """A durable new-front experiment attached to a batch."""

    __tablename__ = "experiments"

    shop_id: Mapped[UUID] = ref("shops.id")
    batch_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False, index=True)
    hypothesis: Mapped[str] = text_column(length=1000)
    experiment_tags: Mapped[list[Any]] = mapped_column(JsonB, nullable=False, default=list)
    product_id: Mapped[UUID | None] = ref("products.id", nullable=True)
    state: Mapped[str] = state(
        "state", ("QUEUED", "RUNNING", "CONCLUDED", "ABANDONED"), default="QUEUED"
    )
    created_at: Mapped[datetime] = moment(default_now=True)
    concluded_at: Mapped[datetime | None] = moment(nullable=True)


class Decision(Identified):
    """A durable, evidence-cited decision, including portfolio verdicts."""

    __tablename__ = "decisions"

    workflow_id: Mapped[UUID] = ref("workflow_runs.id")
    job_id: Mapped[UUID] = ref("jobs.id")
    decision_type: Mapped[str] = text_column(length=100)
    decision: Mapped[str | None] = state("decision", _enum_values(DecisionType), nullable=True)
    branch_outcome: Mapped[str | None] = state(
        "branch_outcome", _enum_values(BranchOutcome), nullable=True
    )
    product_id: Mapped[UUID | None] = ref("products.id", nullable=True)
    listing_id: Mapped[UUID | None] = ref("etsy_listings.id", nullable=True)
    cohort_reference: Mapped[str | None] = text_column(nullable=True)
    rule_version: Mapped[str] = text_column(length=64)
    explanation: Mapped[str] = text_column(length=2000)
    successor_workflow_id: Mapped[UUID | None] = ref("workflow_runs.id", nullable=True)
    successor_spec_id: Mapped[UUID | None] = ref("product_specs.id", nullable=True)
    decided_at: Mapped[datetime] = moment()

    __table_args__ = (
        CheckConstraint(
            "coalesce(decision, '') <> 'MULTIPLY' OR (successor_workflow_id IS NOT NULL"
            " AND successor_workflow_id <> workflow_id AND successor_spec_id IS NOT NULL)",
            name="multiply_creates_a_new_workflow",
        ),
        CheckConstraint(
            "coalesce(decision, '') = 'MULTIPLY'"
            " OR (successor_workflow_id IS NULL AND successor_spec_id IS NULL)",
            name="only_multiply_has_a_successor",
        ),
    )


class DecisionEvidence(Identified):
    """An evidence citation behind one decision. A decision without evidence cannot pass QA."""

    __tablename__ = "decision_evidence"

    decision_id: Mapped[UUID] = ref("decisions.id", ondelete="CASCADE")
    evidence_type: Mapped[str] = text_column(length=100)
    source_reference: Mapped[str] = text_column(length=500)
    artifact_id: Mapped[UUID | None] = ref("artifacts.id", nullable=True)
    metrics_snapshot_id: Mapped[UUID | None] = ref("metrics_snapshots.id", nullable=True)
    observed_at: Mapped[datetime] = moment()

    __table_args__ = (UniqueConstraint("decision_id", "source_reference"),)


class JevEvaluation(Identified):
    """A Jev decision engine evaluation result.

    Records packet, answers, derived results, latency, and model from Jev Gateway evaluate
    calls. May link to a Decision for decision-evidence lineage.
    """

    __tablename__ = "jev_evaluations"

    decision_id: Mapped[UUID | None] = ref("decisions.id", ondelete="SET NULL", nullable=True)
    decision_type: Mapped[str] = text_column(length=100, index=True)
    packet: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False)
    answers: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False)
    derived: Mapped[dict[str, Any] | None] = mapped_column(JsonB, nullable=True)
    model_id: Mapped[str] = text_column(length=100)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluated_at: Mapped[datetime] = moment(default_now=True, index=True)

    __table_args__ = (
        CheckConstraint("latency_ms >= 0", name="latency_non_negative"),
        CheckConstraint("jsonb_typeof(packet) = 'object'", name="packet_is_object"),
        CheckConstraint("jsonb_typeof(answers) = 'object'", name="answers_is_object"),
        CheckConstraint(
            "derived IS NULL OR jsonb_typeof(derived) = 'object'",
            name="derived_is_object_or_null",
        ),
    )


class Incident(Identified):
    """An operational incident, its type and its repair state."""

    __tablename__ = "incidents"

    shop_id: Mapped[UUID] = ref("shops.id")
    incident_type: Mapped[str] = state("incident_type", _enum_values(IncidentType), index=True)
    incident_state: Mapped[str] = state(
        "incident_state", INCIDENT_STATES, default="OPEN", index=True
    )
    affected_object_type: Mapped[str] = text_column(length=100)
    affected_object_id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), nullable=False)
    workflow_id: Mapped[UUID | None] = ref("workflow_runs.id", nullable=True)
    listing_version_id: Mapped[UUID | None] = ref("listing_versions.id", nullable=True)
    opened_by_job_id: Mapped[UUID] = ref("jobs.id")
    resolved_by_job_id: Mapped[UUID | None] = ref("jobs.id", nullable=True)
    safe_detail: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False, default=dict)
    opened_at: Mapped[datetime] = moment(default_now=True)
    resolved_at: Mapped[datetime | None] = moment(nullable=True)

    __table_args__ = (
        CheckConstraint(
            "(incident_state = 'RESOLVED') = (resolved_at IS NOT NULL)",
            name="resolution_requires_a_time",
        ),
    )


class CustomerIssue(Identified):
    """A buyer-reported issue. Personal data is never stored; only a safe reference is."""

    __tablename__ = "customer_issues"

    shop_id: Mapped[UUID] = ref("shops.id")
    listing_id: Mapped[UUID | None] = ref("etsy_listings.id", nullable=True)
    incident_id: Mapped[UUID | None] = ref("incidents.id", nullable=True)
    buyer_reference: Mapped[str] = text_column(length=200)
    issue_state: Mapped[str] = state("issue_state", ISSUE_STATES, default="RECEIVED")
    safe_summary: Mapped[str] = text_column(length=2000)
    received_at: Mapped[datetime] = moment()
    answered_at: Mapped[datetime | None] = moment(nullable=True)

    __table_args__ = (UniqueConstraint("shop_id", "buyer_reference", "received_at"),)


class Receipt(Identified):
    """An append-only receipt for one external effect. Rows are immutable."""

    __tablename__ = "receipts"

    job_id: Mapped[UUID] = ref("jobs.id")
    idempotency_key: Mapped[str] = text_column(length=200)
    provider: Mapped[str] = text_column(length=64)
    operation: Mapped[str] = text_column(length=100)
    side_effect_class: Mapped[str] = state("side_effect_class", _enum_values(SideEffectClass))
    autonomy_mode: Mapped[str] = state("autonomy_mode", _enum_values(AutonomyMode))
    effect_state: Mapped[str] = state("effect_state", EFFECT_STATES)
    provider_object_id: Mapped[str | None] = text_column(nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str | None] = currency(nullable=True)
    safe_detail: Mapped[dict[str, Any]] = mapped_column(JsonB, nullable=False, default=dict)
    recorded_at: Mapped[datetime] = moment(default_now=True)

    __table_args__ = (
        UniqueConstraint("idempotency_key", "operation", "recorded_at"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="nonnegative_amount"),
        CheckConstraint("(amount IS NULL) = (currency IS NULL)", name="amount_needs_a_currency"),
    )


APPEND_ONLY_TABLES: Final = ("events", "receipts")
"""Tables whose rows are immutable. Enforced by a trigger, not by convention alone."""

APPEND_ONLY_FUNCTION_SQL: Final = """
CREATE OR REPLACE FUNCTION money_machine_refuse_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'relation % is append-only; % is refused', TG_TABLE_NAME, TG_OP
        USING ERRCODE = 'restrict_violation';
END;
$$ LANGUAGE plpgsql;
"""
"""Raises rather than returning, so no UPDATE or DELETE can reach an append-only table."""


def append_only_trigger_sql(table: str) -> str:
    """DDL that makes one table refuse updates and deletes."""
    return (
        f"CREATE TRIGGER {table}_are_append_only "
        f"BEFORE UPDATE OR DELETE ON {table} "
        "FOR EACH ROW EXECUTE FUNCTION money_machine_refuse_mutation();"
    )


def _promote_column_checks() -> None:
    """Move column-level CHECK constraints onto their table.

    Alembic's autogenerate reconstructs ``op.create_table`` from a table's own constraint
    collection, so a CHECK attached to a column is silently dropped from the migration.
    Promoting them keeps every taxonomy and invariant constraint in both the metadata and
    the migrated database, which is what the schema tests assert.
    """
    for table in Base.metadata.tables.values():
        for column in table.c:
            for constraint in tuple(column.constraints):
                if isinstance(constraint, CheckConstraint):
                    column.constraints.discard(constraint)
                    table.append_constraint(constraint)


_promote_column_checks()


def install_append_only_triggers(execute: Callable[[str], object]) -> None:
    """Create the refusal function and one trigger per append-only table.

    Alembic's autogenerate does not emit triggers, so the migration calls this explicitly
    and ``tests/integration/test_migrations.py`` asserts the triggers exist in the migrated
    database. Passing the executor in keeps this callable from both Alembic and a test.
    """
    execute(APPEND_ONLY_FUNCTION_SQL)
    for name in APPEND_ONLY_TABLES:
        execute(append_only_trigger_sql(name))


def drop_append_only_triggers(execute: Callable[[str], object]) -> None:
    """Reverse :func:`install_append_only_triggers`."""
    for name in APPEND_ONLY_TABLES:
        execute(f"DROP TRIGGER IF EXISTS {name}_are_append_only ON {name};")
    execute("DROP FUNCTION IF EXISTS money_machine_refuse_mutation();")
