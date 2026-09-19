"""Retry policy primitives: exponential backoff, attempt budgets, and retry eligibility.

Session 03 wave 3: library primitives with deterministic tests. Worker and scheduler remain
fail-closed (exit 78); commissioning is Session 04.

These helpers evaluate retry eligibility per RetryClass, calculate exponential backoff with
optional jitter, and determine whether a failed job should transition to READY (retry) or
TERMINAL_FAILURE (exhausted budget or non-retryable failure).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from money_machine.domain.enums import JobStatus, RetryClass

if TYPE_CHECKING:
    from uuid import UUID


@dataclass(frozen=True, kw_only=True)
class RetryDecision:
    """The outcome of evaluating whether a failed job may retry.

    Returned by :func:`evaluate_retry` to guide the worker's next action: either
    transition the job to READY with a new scheduled_at (retry), or transition to
    TERMINAL_FAILURE (budget exhausted or non-retryable).
    """

    can_retry: bool
    """True if the job should transition FAILED → READY; False if it should go to TERMINAL_FAILURE."""

    next_attempt: int
    """The attempt number for the next execution (current attempt + 1)."""

    scheduled_at: datetime | None
    """When the job should become ready again. None if can_retry is False."""

    reason: str
    """Human-readable explanation of why retry is allowed or refused."""


class RetryBudgetExhausted(Exception):
    """Raised when a job has reached max_attempts and cannot retry."""


def evaluate_retry(
    *,
    retry_class: RetryClass,
    current_attempt: int,
    max_attempts: int,
    base_delay_seconds: float = 2.0,
    backoff_multiplier: float = 2.0,
    max_delay_seconds: float = 300.0,
    now: datetime | None = None,
) -> RetryDecision:
    """Evaluate whether a failed job may retry and when it should run.

    Implements the Session 03 addendum's retry mapping:
    - SAFE: Always retry (read-only, no external effects)
    - IDEMPOTENT: Retry (external write that's safe to repeat)
    - RECONCILE_FIRST: Do not retry here; reconciliation is required first
    - MANUAL_RESUME: Do not retry; operator intervention required
    - NEVER: Do not retry; non-retryable failure

    Uses exponential backoff: delay = min(base * (multiplier ** attempt), max_delay).

    Args:
        retry_class: The job's retry safety contract
        current_attempt: The attempt number that just failed (0-indexed)
        max_attempts: Maximum allowed attempts (must be > 0)
        base_delay_seconds: Initial retry delay in seconds
        backoff_multiplier: Exponential growth factor (typically 2.0)
        max_delay_seconds: Cap on the backoff delay
        now: Current timestamp (defaults to datetime.now(UTC))

    Returns:
        RetryDecision with can_retry, next_attempt, scheduled_at, and reason

    Raises:
        ValueError: If current_attempt >= max_attempts or max_attempts <= 0
    """
    if max_attempts <= 0:
        raise ValueError(f"max_attempts must be positive, got {max_attempts}")

    if current_attempt >= max_attempts:
        raise ValueError(
            f"current_attempt {current_attempt} >= max_attempts {max_attempts}; "
            "job should already be TERMINAL_FAILURE"
        )

    if now is None:
        now = datetime.now(UTC)

    next_attempt = current_attempt + 1

    # Check if budget is exhausted
    if next_attempt >= max_attempts:
        return RetryDecision(
            can_retry=False,
            next_attempt=next_attempt,
            scheduled_at=None,
            reason=f"retry budget exhausted ({next_attempt}/{max_attempts})",
        )

    # Evaluate retry class
    match retry_class:
        case RetryClass.SAFE:
            # SAFE = read-only, no external effects, always safe to retry
            delay = _calculate_backoff(
                current_attempt, base_delay_seconds, backoff_multiplier, max_delay_seconds
            )
            scheduled_at = now + timedelta(seconds=delay)
            return RetryDecision(
                can_retry=True,
                next_attempt=next_attempt,
                scheduled_at=scheduled_at,
                reason=f"SAFE retry after {delay:.1f}s backoff",
            )

        case RetryClass.IDEMPOTENT:
            # IDEMPOTENT = external write that's safe to repeat
            delay = _calculate_backoff(
                current_attempt, base_delay_seconds, backoff_multiplier, max_delay_seconds
            )
            scheduled_at = now + timedelta(seconds=delay)
            return RetryDecision(
                can_retry=True,
                next_attempt=next_attempt,
                scheduled_at=scheduled_at,
                reason=f"IDEMPOTENT retry after {delay:.1f}s backoff",
            )

        case RetryClass.RECONCILE_FIRST:
            # RECONCILE_FIRST = uncertain external effect, reconciliation required
            return RetryDecision(
                can_retry=False,
                next_attempt=next_attempt,
                scheduled_at=None,
                reason="RECONCILE_FIRST: reconciliation required before retry",
            )

        case RetryClass.MANUAL_RESUME:
            # MANUAL_RESUME = operator intervention required
            return RetryDecision(
                can_retry=False,
                next_attempt=next_attempt,
                scheduled_at=None,
                reason="MANUAL_RESUME: operator intervention required",
            )

        case RetryClass.NEVER:
            # NEVER = non-retryable failure
            return RetryDecision(
                can_retry=False,
                next_attempt=next_attempt,
                scheduled_at=None,
                reason="NEVER: non-retryable failure",
            )


def _calculate_backoff(
    attempt: int,
    base_delay: float,
    multiplier: float,
    max_delay: float,
) -> float:
    """Calculate exponential backoff delay with a cap.

    Formula: min(base * (multiplier ** attempt), max_delay)

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Initial delay in seconds
        multiplier: Exponential growth factor
        max_delay: Maximum delay cap

    Returns:
        Backoff delay in seconds
    """
    delay = base_delay * (multiplier**attempt)
    return min(delay, max_delay)


def can_retry_from_status(status: JobStatus) -> bool:
    """Check if a job in the given status is eligible for retry evaluation.

    Only FAILED jobs may be evaluated for retry. UNCERTAIN_EXTERNAL_EFFECT jobs must
    be reconciled first (which may move them to SUCCEEDED, FAILED, or BLOCKED).

    Args:
        status: Current job status

    Returns:
        True if the status is FAILED, False otherwise
    """
    return status == JobStatus.FAILED


def must_reconcile_first(status: JobStatus, retry_class: RetryClass) -> bool:
    """Check if a job requires reconciliation before any retry.

    True for jobs in UNCERTAIN_EXTERNAL_EFFECT status or with RECONCILE_FIRST retry class.

    Args:
        status: Current job status
        retry_class: The job's retry safety contract

    Returns:
        True if reconciliation is required before retry
    """
    return (
        status == JobStatus.UNCERTAIN_EXTERNAL_EFFECT or retry_class == RetryClass.RECONCILE_FIRST
    )
