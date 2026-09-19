"""Unit tests for retry policy primitives.

Deterministic tests for exponential backoff, retry eligibility, and retry class evaluation
per the Session 03 wave 3 requirements.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from money_machine.domain.enums import JobStatus, RetryClass
from money_machine.orchestration.retry import (
    RetryDecision,
    can_retry_from_status,
    evaluate_retry,
    must_reconcile_first,
)


def test_evaluate_retry_safe_first_attempt() -> None:
    """SAFE jobs retry with exponential backoff after first failure."""
    now = datetime(2026, 9, 19, 0, 0, 0, tzinfo=UTC)

    decision = evaluate_retry(
        retry_class=RetryClass.SAFE,
        current_attempt=0,
        max_attempts=3,
        base_delay_seconds=2.0,
        backoff_multiplier=2.0,
        now=now,
    )

    assert decision.can_retry is True
    assert decision.next_attempt == 1
    assert decision.scheduled_at == now + timedelta(seconds=2.0)
    assert "SAFE retry after 2.0s backoff" in decision.reason


def test_evaluate_retry_safe_second_attempt() -> None:
    """SAFE jobs use exponential backoff: 2.0 * (2.0 ** 1) = 4.0s."""
    now = datetime(2026, 9, 19, 0, 0, 0, tzinfo=UTC)

    decision = evaluate_retry(
        retry_class=RetryClass.SAFE,
        current_attempt=1,
        max_attempts=3,
        base_delay_seconds=2.0,
        backoff_multiplier=2.0,
        now=now,
    )

    assert decision.can_retry is True
    assert decision.next_attempt == 2
    assert decision.scheduled_at == now + timedelta(seconds=4.0)
    assert "SAFE retry after 4.0s backoff" in decision.reason


def test_evaluate_retry_safe_third_attempt_hits_budget() -> None:
    """SAFE jobs exhaust budget at max_attempts."""
    now = datetime(2026, 9, 19, 0, 0, 0, tzinfo=UTC)

    decision = evaluate_retry(
        retry_class=RetryClass.SAFE,
        current_attempt=2,
        max_attempts=3,
        base_delay_seconds=2.0,
        backoff_multiplier=2.0,
        now=now,
    )

    assert decision.can_retry is False
    assert decision.next_attempt == 3
    assert decision.scheduled_at is None
    assert "retry budget exhausted (3/3)" in decision.reason


def test_evaluate_retry_idempotent_retries_with_backoff() -> None:
    """IDEMPOTENT jobs retry with exponential backoff like SAFE."""
    now = datetime(2026, 9, 19, 0, 0, 0, tzinfo=UTC)

    decision = evaluate_retry(
        retry_class=RetryClass.IDEMPOTENT,
        current_attempt=0,
        max_attempts=3,
        base_delay_seconds=2.0,
        backoff_multiplier=2.0,
        now=now,
    )

    assert decision.can_retry is True
    assert decision.next_attempt == 1
    assert decision.scheduled_at == now + timedelta(seconds=2.0)
    assert "IDEMPOTENT retry after 2.0s backoff" in decision.reason


def test_evaluate_retry_reconcile_first_does_not_retry() -> None:
    """RECONCILE_FIRST jobs must be reconciled before any retry."""
    now = datetime(2026, 9, 19, 0, 0, 0, tzinfo=UTC)

    decision = evaluate_retry(
        retry_class=RetryClass.RECONCILE_FIRST,
        current_attempt=0,
        max_attempts=3,
        base_delay_seconds=2.0,
        backoff_multiplier=2.0,
        now=now,
    )

    assert decision.can_retry is False
    assert decision.next_attempt == 1
    assert decision.scheduled_at is None
    assert "RECONCILE_FIRST: reconciliation required before retry" in decision.reason


def test_evaluate_retry_manual_resume_does_not_retry() -> None:
    """MANUAL_RESUME jobs require operator intervention."""
    now = datetime(2026, 9, 19, 0, 0, 0, tzinfo=UTC)

    decision = evaluate_retry(
        retry_class=RetryClass.MANUAL_RESUME,
        current_attempt=0,
        max_attempts=3,
        base_delay_seconds=2.0,
        backoff_multiplier=2.0,
        now=now,
    )

    assert decision.can_retry is False
    assert decision.next_attempt == 1
    assert decision.scheduled_at is None
    assert "MANUAL_RESUME: operator intervention required" in decision.reason


def test_evaluate_retry_never_does_not_retry() -> None:
    """NEVER jobs are non-retryable failures."""
    now = datetime(2026, 9, 19, 0, 0, 0, tzinfo=UTC)

    decision = evaluate_retry(
        retry_class=RetryClass.NEVER,
        current_attempt=0,
        max_attempts=3,
        base_delay_seconds=2.0,
        backoff_multiplier=2.0,
        now=now,
    )

    assert decision.can_retry is False
    assert decision.next_attempt == 1
    assert decision.scheduled_at is None
    assert "NEVER: non-retryable failure" in decision.reason


def test_evaluate_retry_backoff_cap() -> None:
    """Exponential backoff is capped at max_delay_seconds."""
    now = datetime(2026, 9, 19, 0, 0, 0, tzinfo=UTC)

    # After 5 attempts: 2.0 * (2.0 ** 5) = 64.0s, but cap at 30.0s
    decision = evaluate_retry(
        retry_class=RetryClass.SAFE,
        current_attempt=5,
        max_attempts=10,
        base_delay_seconds=2.0,
        backoff_multiplier=2.0,
        max_delay_seconds=30.0,
        now=now,
    )

    assert decision.can_retry is True
    assert decision.next_attempt == 6
    assert decision.scheduled_at == now + timedelta(seconds=30.0)
    assert "SAFE retry after 30.0s backoff" in decision.reason


def test_evaluate_retry_raises_on_invalid_max_attempts() -> None:
    """evaluate_retry raises ValueError if max_attempts <= 0."""
    now = datetime(2026, 9, 19, 0, 0, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="max_attempts must be positive"):
        evaluate_retry(
            retry_class=RetryClass.SAFE,
            current_attempt=0,
            max_attempts=0,
            now=now,
        )


def test_evaluate_retry_raises_on_exhausted_budget() -> None:
    """evaluate_retry raises ValueError if current_attempt >= max_attempts."""
    now = datetime(2026, 9, 19, 0, 0, 0, tzinfo=UTC)

    with pytest.raises(ValueError, match="current_attempt.*>= max_attempts"):
        evaluate_retry(
            retry_class=RetryClass.SAFE,
            current_attempt=3,
            max_attempts=3,
            now=now,
        )


def test_can_retry_from_status_only_failed() -> None:
    """Only FAILED jobs are eligible for retry evaluation."""
    assert can_retry_from_status(JobStatus.FAILED) is True
    assert can_retry_from_status(JobStatus.PENDING) is False
    assert can_retry_from_status(JobStatus.BLOCKED) is False
    assert can_retry_from_status(JobStatus.READY) is False
    assert can_retry_from_status(JobStatus.RUNNING) is False
    assert can_retry_from_status(JobStatus.SUCCEEDED) is False
    assert can_retry_from_status(JobStatus.TERMINAL_FAILURE) is False
    assert can_retry_from_status(JobStatus.CANCELLED) is False
    assert can_retry_from_status(JobStatus.UNCERTAIN_EXTERNAL_EFFECT) is False


def test_must_reconcile_first_for_uncertain_status() -> None:
    """UNCERTAIN_EXTERNAL_EFFECT jobs must reconcile first."""
    assert must_reconcile_first(JobStatus.UNCERTAIN_EXTERNAL_EFFECT, RetryClass.SAFE) is True
    assert must_reconcile_first(JobStatus.UNCERTAIN_EXTERNAL_EFFECT, RetryClass.IDEMPOTENT) is True
    assert must_reconcile_first(JobStatus.UNCERTAIN_EXTERNAL_EFFECT, RetryClass.NEVER) is True


def test_must_reconcile_first_for_reconcile_first_class() -> None:
    """RECONCILE_FIRST retry class requires reconciliation before retry."""
    assert must_reconcile_first(JobStatus.FAILED, RetryClass.RECONCILE_FIRST) is True
    assert must_reconcile_first(JobStatus.BLOCKED, RetryClass.RECONCILE_FIRST) is True
    assert must_reconcile_first(JobStatus.READY, RetryClass.RECONCILE_FIRST) is True


def test_must_reconcile_first_false_for_other_cases() -> None:
    """Other status/class combinations don't require reconciliation."""
    assert must_reconcile_first(JobStatus.FAILED, RetryClass.SAFE) is False
    assert must_reconcile_first(JobStatus.FAILED, RetryClass.IDEMPOTENT) is False
    assert must_reconcile_first(JobStatus.SUCCEEDED, RetryClass.RECONCILE_FIRST) is False


def test_retry_decision_is_immutable() -> None:
    """RetryDecision is a frozen dataclass."""
    now = datetime(2026, 9, 19, 0, 0, 0, tzinfo=UTC)
    decision = RetryDecision(
        can_retry=True,
        next_attempt=1,
        scheduled_at=now,
        reason="test",
    )

    with pytest.raises((AttributeError, TypeError)):
        decision.can_retry = False  # type: ignore[misc]
