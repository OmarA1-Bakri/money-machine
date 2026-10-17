"""Earn the Session 10 metrics and maturity keys from injected fixtures.

The proof does not open a socket, read a credential, insert a job, or schedule a timer.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from money_machine.assets.maturity_clock import (
    ACCUMULATED_LIVE_RULE,
    MATURITY_LIVE_DAYS,
    ListingDefect,
    LiveInterval,
    evaluate_maturity,
    repair_work_id,
)
from money_machine.assets.metrics_fixture import (
    ActiveListing,
    MetricsFixtureRefusal,
    MilestoneInput,
    derive_milestones,
    plan_monthly,
    plan_weekly,
    snapshots_from_fixture,
)
from money_machine.domain.models.common import EvidenceReference

METRICS_EVIDENCE_KEY = "metrics_fixture_implemented"
MATURITY_EVIDENCE_KEY = "maturity_clock_implemented"
EARNED_EVIDENCE_KEYS = frozenset({METRICS_EVIDENCE_KEY, MATURITY_EVIDENCE_KEY})
_PUBLISHED = datetime(2026, 3, 1, tzinfo=UTC)
_LISTING = UUID("00000000-0000-4000-8000-0000000000a1")
_START = datetime(2026, 10, 5, tzinfo=UTC)
_END = datetime(2026, 10, 12, tzinfo=UTC)
_OBSERVED = datetime(2026, 10, 12, 9, tzinfo=UTC)


class Session10ProofError(ValueError):
    """The Session 10 fixture did not earn its evidence key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def prove_session_10() -> frozenset[str]:
    """Return the metrics and maturity keys. A miss raises instead of returning them."""
    _prove_metrics()
    _prove_maturity()
    return EARNED_EVIDENCE_KEYS


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


def _prove_maturity() -> None:
    paused = _paused_listing()
    calendar_day = evaluate_maturity(
        listing_id=_LISTING,
        published_at=_PUBLISHED,
        intervals=paused,
        evaluated_at=_at_hours(24 * 30),
    )
    if (
        calendar_day.accumulated_live_periods != 20
        or calendar_day.mature
        or calendar_day.portfolio_decision_due
        or calendar_day.repair is not None
        or calendar_day.idempotency_key is not None
    ):
        raise Session10ProofError("maturity_paused")
    stored = evaluate_maturity(
        listing_id=_LISTING,
        published_at=_PUBLISHED,
        intervals=paused,
        evaluated_at=_at_hours(24 * 30),
        live_days=30,
    )
    if stored.mature or stored.accumulated_live_periods != 20 or stored.idempotency_key is not None:
        raise Session10ProofError("maturity_stored_days")
    detected_at = _at_hours(24)
    defect = ListingDefect(code="broken_link", detected_at=detected_at)
    repair = evaluate_maturity(
        listing_id=_LISTING,
        published_at=_PUBLISHED,
        intervals=(_span("ACTIVE", 0, 24 * 5),),
        evaluated_at=_at_hours(24 * 5),
        defect=defect,
    )
    if (
        repair.mature
        or repair.portfolio_decision_due
        or repair.idempotency_key is not None
        or repair.repair is None
        or repair.repair.repair_job_id != repair_work_id(_LISTING, "broken_link")
        or repair.repair.detected_at != detected_at
    ):
        raise Session10ProofError("maturity_repair")
    after_pause = 24 * 30
    due = evaluate_maturity(
        listing_id=_LISTING,
        published_at=_PUBLISHED,
        intervals=(*paused, _span("ACTIVE", after_pause, after_pause + 24 * 10)),
        evaluated_at=_at_hours(after_pause + 24 * 10),
    )
    expected = f"{_LISTING}:{ACCUMULATED_LIVE_RULE}:{MATURITY_LIVE_DAYS}"
    calendar_name = (_PUBLISHED + timedelta(days=30)).isoformat()
    if (
        due.accumulated_live_periods != 30
        or not due.mature
        or not due.portfolio_decision_due
        or due.idempotency_key != expected
        or calendar_name in expected
    ):
        raise Session10ProofError("maturity_due")
    source = Path(evaluate_maturity.__code__.co_filename).read_text(encoding="utf-8")
    if "schedule_maturity_timer" in source or "orchestration.scheduler" in source:
        raise Session10ProofError("maturity_scheduler")


def _prove_metrics() -> None:
    listing_id = uuid4()
    shop_id = uuid4()
    evidence = EvidenceReference(
        evidence_id=uuid4(),
        evidence_type="provider-observation",
        source_reference="fixture://metrics/week",
        observed_at=_OBSERVED,
        safe_summary="Injected weekly metrics citation",
    )
    row = {
        "snapshot_id": uuid4(),
        "listing_id": listing_id,
        "listing_version": 1,
        "provider": "etsy",
        "observed_at": _OBSERVED,
        "views": 4,
        "favourites": 1,
        "orders": 1,
        "gross_revenue": Decimal("12.50"),
        "currency": "GBP",
        "reconciled": True,
        "window_start": _START,
        "window_end": _END,
        "evidence": evidence,
    }
    loaded = snapshots_from_fixture((row,))
    if len(loaded) != 1 or loaded[0].snapshot.views != 4 or not loaded[0].snapshot.reconciled:
        raise Session10ProofError("metrics_snapshot")
    try:
        snapshots_from_fixture((row, row))
    except MetricsFixtureRefusal as error:
        if error.code != "duplicate_listing_window":
            raise Session10ProofError("metrics_duplicate") from error
    else:
        raise Session10ProofError("metrics_duplicate")
    listings = (
        ActiveListing(listing_id=listing_id, listing_version=1, active=True),
        ActiveListing(listing_id=uuid4(), listing_version=1, active=False),
    )
    plan = plan_weekly(
        listings,
        window_start=_START,
        window_end=_END,
        prior_snapshots=(loaded[0].snapshot,),
    )
    if [record.kind for record in plan.records] != ["collection", "shop_review"]:
        raise Session10ProofError("metrics_weekly")
    if plan.prior_snapshots != (loaded[0].snapshot,):
        raise Session10ProofError("metrics_prior")
    again = plan_weekly(
        listings,
        window_start=_START,
        window_end=_END,
        prior_snapshots=(loaded[0].snapshot,),
        existing_records=plan.records,
    )
    if again.records:
        raise Session10ProofError("metrics_second_window")
    skipped = plan_monthly(
        cadence="monthly",
        weekly_fire_count=4,
        month_due=False,
        window_start=_START,
        window_end=_END,
        shop_id=shop_id,
    )
    if skipped is not None:
        raise Session10ProofError("metrics_fourth_week")
    monthly = plan_monthly(
        cadence="monthly",
        weekly_fire_count=4,
        month_due=True,
        window_start=_START,
        window_end=_END,
        shop_id=shop_id,
    )
    if monthly is None or monthly.cadence != "monthly" or len(monthly.jobs) != 3:
        raise Session10ProofError("metrics_monthly")
    try:
        plan_monthly(
            cadence="weekly",
            weekly_fire_count=1,
            month_due=True,
            window_start=_START,
            window_end=_END,
            shop_id=shop_id,
        )
    except MetricsFixtureRefusal as error:
        if error.code != "cadence":
            raise Session10ProofError("metrics_cadence") from error
    else:
        raise Session10ProofError("metrics_cadence")
    try:
        derive_milestones(
            MilestoneInput(
                effects=(),
                successor_spec_id=None,
                measured=False,
                operator_minutes=0,
            )
        )
    except MetricsFixtureRefusal as error:
        if error.code != "unmeasured_operator_minutes":
            raise Session10ProofError("metrics_minutes") from error
    else:
        raise Session10ProofError("metrics_minutes")
