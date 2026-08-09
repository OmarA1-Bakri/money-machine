"""Enumerations frozen for the first-product vertical slice."""

from enum import StrEnum


class QualificationDimension(StrEnum):
    """The four playbook-backed product qualification dimensions."""

    DEMAND = "demand"
    DIFFERENTIATION = "differentiation"
    BUILD_FEASIBILITY = "build_feasibility"
    BUYER_VALUE = "buyer_value"


class ProductState(StrEnum):
    """Durable first-product workflow states."""

    RESEARCHED = "RESEARCHED"
    QUALIFIED = "QUALIFIED"
    SPECIFIED = "SPECIFIED"
    DEDUPE_PASSED = "DEDUPE_PASSED"
    BUILT = "BUILT"
    QA_PASSED = "QA_PASSED"
    MERCHANDISED = "MERCHANDISED"
    PREFLIGHT_PASSED = "PREFLIGHT_PASSED"
    DRAFT_READY = "DRAFT_READY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


class JobState(StrEnum):
    """Durable job lifecycle states."""

    PENDING = "PENDING"
    READY = "READY"
    LEASED = "LEASED"
    RUNNING = "RUNNING"
    RETRY_WAIT = "RETRY_WAIT"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RetryClass(StrEnum):
    """Failure handling classes shared by jobs and attempts."""

    NEVER = "NEVER"
    TRANSIENT_INTERNAL = "TRANSIENT_INTERNAL"
    TRANSIENT_PROVIDER_READ = "TRANSIENT_PROVIDER_READ"
    RECONCILE_EXTERNAL_EFFECT = "RECONCILE_EXTERNAL_EFFECT"
    OPERATOR_REQUIRED = "OPERATOR_REQUIRED"
