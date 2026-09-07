"""Canonical domain taxonomies for Session 01 contracts."""

from enum import StrEnum


class ProductLifecycleState(StrEnum):
    """Durable product experiment lifecycle states."""

    DISCOVERED = "DISCOVERED"
    RESEARCHING = "RESEARCHING"
    RESEARCH_COMPLETE = "RESEARCH_COMPLETE"
    QUALIFYING = "QUALIFYING"
    QUALIFIED = "QUALIFIED"
    REJECTED = "REJECTED"
    TEARDOWN_PENDING = "TEARDOWN_PENDING"
    TEARDOWN_COMPLETE = "TEARDOWN_COMPLETE"
    SPEC_READY = "SPEC_READY"
    DEDUPE_CHECK = "DEDUPE_CHECK"
    RECONCEPTING = "RECONCEPTING"
    BUILDING = "BUILDING"
    BUILD_QA = "BUILD_QA"
    BUILD_REPAIR = "BUILD_REPAIR"
    VARIANT_BUILD = "VARIANT_BUILD"
    VARIANT_QA = "VARIANT_QA"
    MERCHANDISING = "MERCHANDISING"
    ASSET_BUILD = "ASSET_BUILD"
    ASSET_QA = "ASSET_QA"
    DRAFTING = "DRAFTING"
    DRAFT_READY = "DRAFT_READY"
    PREFLIGHT = "PREFLIGHT"
    LISTING_REPAIR = "LISTING_REPAIR"
    READY_TO_PUBLISH = "READY_TO_PUBLISH"
    PUBLISHED = "PUBLISHED"
    POST_PUBLISH_QA = "POST_PUBLISH_QA"
    INCIDENT_REPAIR = "INCIDENT_REPAIR"
    OBSERVING = "OBSERVING"
    MATURE = "MATURE"
    EVALUATING = "EVALUATING"
    REPAIRING = "REPAIRING"
    DEACTIVATING = "DEACTIVATING"
    DEACTIVATED = "DEACTIVATED"
    SUCCESSOR_SPEC = "SUCCESSOR_SPEC"


class JobStatus(StrEnum):
    """Durable orchestration job states."""

    PENDING = "PENDING"
    BLOCKED = "BLOCKED"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TERMINAL_FAILURE = "TERMINAL_FAILURE"
    CANCELLED = "CANCELLED"
    UNCERTAIN_EXTERNAL_EFFECT = "UNCERTAIN_EXTERNAL_EFFECT"


class AgentRunStatus(StrEnum):
    """Terminal statuses returned by one agent run."""

    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    BLOCKED = "BLOCKED"
    UNCERTAIN_EXTERNAL_EFFECT = "UNCERTAIN_EXTERNAL_EFFECT"


class BranchOutcome(StrEnum):
    """Non-state results that select a lifecycle transition."""

    PASS = "PASS"
    FAIL = "FAIL"
    TOO_CLOSE = "TOO_CLOSE"


class SideEffectClass(StrEnum):
    """External-effect classification for a job."""

    NONE = "NONE"
    EXTERNAL_READ = "EXTERNAL_READ"
    EXTERNAL_WRITE = "EXTERNAL_WRITE"
    EXTERNAL_SPEND = "EXTERNAL_SPEND"
    EXTERNAL_MESSAGE = "EXTERNAL_MESSAGE"


class RetryClass(StrEnum):
    """Retry safety contract for a job."""

    SAFE = "SAFE"
    IDEMPOTENT = "IDEMPOTENT"
    RECONCILE_FIRST = "RECONCILE_FIRST"
    MANUAL_RESUME = "MANUAL_RESUME"
    NEVER = "NEVER"


class DecisionType(StrEnum):
    """Portfolio decisions available after evaluation."""

    HOLD = "HOLD"
    REPAIR = "REPAIR"
    CULL = "CULL"
    MULTIPLY = "MULTIPLY"


class IncidentType(StrEnum):
    """Canonical incident categories that require durable resolution."""

    BROKEN_LINK = "BROKEN_LINK"
    CUSTOMER_ISSUE = "CUSTOMER_ISSUE"
    BUILD_DEFECT = "BUILD_DEFECT"
    LISTING_DEFECT = "LISTING_DEFECT"
    CREDENTIAL_FAILURE = "CREDENTIAL_FAILURE"
    PROVIDER_MISMATCH = "PROVIDER_MISMATCH"
    TERMINAL_JOB_FAILURE = "TERMINAL_JOB_FAILURE"
    UNCERTAIN_EXTERNAL_EFFECT = "UNCERTAIN_EXTERNAL_EFFECT"


class AutonomyMode(StrEnum):
    """Standing-authority operating modes."""

    SIMULATION = "simulation"
    DRAFT = "draft"
    LIVE = "live"


class CapabilityChannel(StrEnum):
    """Selected implementation channel, independent from authority and availability."""

    DIRECT_API = "DIRECT_API"
    COMPOSIO = "COMPOSIO"
    BROWSER = "BROWSER"
    INTERNAL_RENDERER = "INTERNAL_RENDERER"
    MANUAL_EXTERNAL_BLOCKER = "MANUAL_EXTERNAL_BLOCKER"
