"""Thirty accumulated live UTC periods. Paused time is not maturity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Literal
from uuid import UUID

from money_machine.assets.maturity_clock import (
    ACCUMULATED_LIVE_RULE,
    MATURITY_LIVE_DAYS,
    ListingDefect,
    LiveInterval,
    evaluate_maturity,
    repair_work_id,
)

_LISTING = UUID("00000000-0000-4000-8000-0000000000a1")
_OTHER = UUID("00000000-0000-4000-8000-0000000000a2")
_PUBLISHED = datetime(2026, 3, 1, tzinfo=UTC)


def _at_hours(hours: int) -> datetime:
    return _PUBLISHED + timedelta(hours=hours)


def _span(
    status: Literal["ACTIVE", "INACTIVE"],
    start_hour: int,
    end_hour: int,
) -> LiveInterval:
    return LiveInterval(
        status=status,
        started_at=_at_hours(start_hour),
        ended_at=_at_hours(end_hour),
    )


def _paused_listing() -> tuple[LiveInterval, ...]:
    """Twenty live periods, then ten inactive periods. Calendar length is 30 days."""
    return (
        _span("ACTIVE", 0, 24 * 20),
        _span("INACTIVE", 24 * 20, 24 * 30),
    )


def test_paused_listing_is_not_mature_on_calendar_day_30() -> None:
    evaluated_at = _PUBLISHED + timedelta(days=30)
    assert evaluated_at == _at_hours(24 * 30)
    result = evaluate_maturity(
        listing_id=_LISTING,
        published_at=_PUBLISHED,
        intervals=_paused_listing(),
        evaluated_at=evaluated_at,
    )
    assert result.accumulated_live_periods == 20
    assert result.mature is False
    assert result.portfolio_decision_due is False
    assert result.repair is None
    assert result.idempotency_key is None


def test_maturity_requires_thirty_active_periods_and_ignores_trailing_hours() -> None:
    paused = _paused_listing()
    after_pause = 24 * 30

    hours_do_not_count = evaluate_maturity(
        listing_id=_LISTING,
        published_at=_PUBLISHED,
        intervals=(*paused, _span("ACTIVE", after_pause, after_pause + 23)),
        evaluated_at=_at_hours(after_pause + 23),
    )
    assert _at_hours(after_pause + 23) > _PUBLISHED + timedelta(days=30)
    assert hours_do_not_count.accumulated_live_periods == 20
    assert hours_do_not_count.mature is False
    assert hours_do_not_count.portfolio_decision_due is False

    partial_period = evaluate_maturity(
        listing_id=_LISTING,
        published_at=_PUBLISHED,
        intervals=(*paused, _span("ACTIVE", after_pause, after_pause + 24 * 9 + 23)),
        evaluated_at=_at_hours(after_pause + 24 * 9 + 23),
    )
    assert partial_period.accumulated_live_periods == 29
    assert partial_period.mature is False
    assert partial_period.portfolio_decision_due is False

    thirty_live = evaluate_maturity(
        listing_id=_LISTING,
        published_at=_PUBLISHED,
        intervals=(*paused, _span("ACTIVE", after_pause, after_pause + 24 * 10)),
        evaluated_at=_at_hours(after_pause + 24 * 10),
    )
    assert thirty_live.accumulated_live_periods == 30
    assert thirty_live.mature is True
    assert thirty_live.portfolio_decision_due is True
    assert thirty_live.idempotency_key != (_PUBLISHED + timedelta(days=30)).isoformat()


def test_stored_live_days_does_not_override_intervals() -> None:
    result = evaluate_maturity(
        listing_id=_LISTING,
        published_at=_PUBLISHED,
        intervals=_paused_listing(),
        evaluated_at=_at_hours(24 * 30),
        live_days=30,
    )
    assert result.accumulated_live_periods == 20
    assert result.mature is False
    assert result.portfolio_decision_due is False
    assert result.idempotency_key is None


def test_defect_inside_the_window_returns_repair_data_immediately() -> None:
    detected_at = _at_hours(24)
    evaluated_at = _at_hours(24 * 5)
    assert evaluated_at < _PUBLISHED + timedelta(days=30)
    defect = ListingDefect(code="broken_link", detected_at=detected_at)
    result = evaluate_maturity(
        listing_id=_LISTING,
        published_at=_PUBLISHED,
        intervals=(_span("ACTIVE", 0, 24 * 5),),
        evaluated_at=evaluated_at,
        defect=defect,
    )
    assert result.accumulated_live_periods == 5
    assert result.mature is False
    assert result.portfolio_decision_due is False
    assert result.idempotency_key is None
    assert result.repair is not None
    assert result.repair.repair_job_id == repair_work_id(_LISTING, "broken_link")
    assert result.repair.listing_id == _LISTING
    assert result.repair.defect_code == "broken_link"
    assert result.repair.detected_at == detected_at
    assert result.repair.detected_at != _PUBLISHED + timedelta(days=30)
    assert getattr(result.repair, "__tablename__", None) is None
    assert not hasattr(result.repair, "status")
    assert not hasattr(result.repair, "_sa_instance_state")
    again = evaluate_maturity(
        listing_id=_LISTING,
        published_at=_PUBLISHED,
        intervals=(_span("ACTIVE", 0, 24 * 5),),
        evaluated_at=evaluated_at,
        defect=defect,
    )
    assert again.repair == result.repair


def test_due_result_uses_a_stable_accumulated_live_idempotency_key() -> None:
    after_pause = 24 * 30
    due_at = _at_hours(after_pause + 24 * 10)
    intervals = (*_paused_listing(), _span("ACTIVE", after_pause, after_pause + 24 * 10))
    started = perf_counter()
    result = evaluate_maturity(
        listing_id=_LISTING,
        published_at=_PUBLISHED,
        intervals=intervals,
        evaluated_at=due_at,
    )
    elapsed = perf_counter() - started
    later = evaluate_maturity(
        listing_id=_LISTING,
        published_at=_PUBLISHED,
        intervals=intervals,
        evaluated_at=due_at + timedelta(days=3),
    )
    other = evaluate_maturity(
        listing_id=_OTHER,
        published_at=_PUBLISHED,
        intervals=intervals,
        evaluated_at=due_at,
    )
    calendar_due = (_PUBLISHED + timedelta(days=30)).isoformat()
    expected = f"{_LISTING}:{ACCUMULATED_LIVE_RULE}:{MATURITY_LIVE_DAYS}"
    key = result.idempotency_key
    assert key is not None
    assert elapsed < 1
    assert result.portfolio_decision_due is True
    assert key == expected
    assert later.idempotency_key == expected
    assert other.idempotency_key == f"{_OTHER}:{ACCUMULATED_LIVE_RULE}:{MATURITY_LIVE_DAYS}"
    assert other.idempotency_key != key
    assert key != calendar_due
    assert calendar_due not in key
    assert "30 days" not in key
    source = Path(evaluate_maturity.__code__.co_filename).read_text(encoding="utf-8")
    assert "schedule_maturity_timer" not in source
    assert "orchestration.scheduler" not in source
    assert "time.sleep" not in source
    assert "asyncio.sleep" not in source
