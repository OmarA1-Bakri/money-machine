"""Publication-ramp predicate. Each pin is its own test."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from money_machine.assets.publishing_ramp_decision import decide_publishing_ramp
from money_machine.config import PublishingRampConfig, load_yaml_model

_RAMP_FILE = Path(__file__).resolve().parents[3] / "config" / "publishing_ramp.yaml"
_OLDEST = datetime(2026, 10, 9, 15, 30, tzinfo=UTC)


def test_disabled_publishing_waits_at_reconciled_count_zero() -> None:
    ramp = load_yaml_model(_RAMP_FILE, PublishingRampConfig)
    assert ramp.publishing_enabled is False
    assert ramp.initial_weekly_cap == 2

    decision = decide_publishing_ramp(
        publishing_enabled=ramp.publishing_enabled,
        initial_weekly_cap=ramp.initial_weekly_cap,
        hard_weekly_cap=ramp.hard_weekly_cap,
        rolling_window_days=ramp.rolling_window_days,
        reconciled_count=0,
        oldest_reconciled_at=None,
        unreconciled_count=0,
    )

    assert decision.may_publish is False
    assert decision.next_permissible_at is None


def test_reconciled_count_at_the_supplied_cap_waits_for_the_window() -> None:
    initial_weekly_cap = 2
    rolling_window_days = 7
    decision = decide_publishing_ramp(
        publishing_enabled=True,
        initial_weekly_cap=initial_weekly_cap,
        hard_weekly_cap=15,
        rolling_window_days=rolling_window_days,
        reconciled_count=initial_weekly_cap,
        oldest_reconciled_at=_OLDEST,
        unreconciled_count=0,
    )

    assert decision.may_publish is False
    assert decision.next_permissible_at == _OLDEST + timedelta(days=rolling_window_days)


def test_reconciled_count_one_below_the_cap_may_publish() -> None:
    initial_weekly_cap = 2
    decision = decide_publishing_ramp(
        publishing_enabled=True,
        initial_weekly_cap=initial_weekly_cap,
        hard_weekly_cap=15,
        rolling_window_days=7,
        reconciled_count=initial_weekly_cap - 1,
        oldest_reconciled_at=_OLDEST,
        unreconciled_count=0,
    )

    assert decision.may_publish is True
    assert decision.next_permissible_at is None


def test_unreconciled_publication_does_not_increment_the_count() -> None:
    initial_weekly_cap = 2
    decision = decide_publishing_ramp(
        publishing_enabled=True,
        initial_weekly_cap=initial_weekly_cap,
        hard_weekly_cap=15,
        rolling_window_days=7,
        reconciled_count=initial_weekly_cap - 1,
        oldest_reconciled_at=_OLDEST,
        unreconciled_count=1,
    )

    assert decision.may_publish is True
    assert decision.next_permissible_at is None


def test_caller_supplied_initial_cap_of_three_changes_the_wait_point() -> None:
    decision = decide_publishing_ramp(
        publishing_enabled=True,
        initial_weekly_cap=3,
        hard_weekly_cap=15,
        rolling_window_days=7,
        reconciled_count=2,
        oldest_reconciled_at=_OLDEST,
        unreconciled_count=0,
    )

    assert decision.may_publish is True
    assert decision.next_permissible_at is None


def test_cap_above_hard_weekly_cap_is_not_publishable() -> None:
    decision = decide_publishing_ramp(
        publishing_enabled=True,
        initial_weekly_cap=16,
        hard_weekly_cap=15,
        rolling_window_days=7,
        reconciled_count=15,
        oldest_reconciled_at=_OLDEST,
        unreconciled_count=0,
    )

    assert decision.may_publish is False
