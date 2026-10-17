"""Earn the Session 10 metrics, maturity, and portfolio keys from injected fixtures.

The proof does not open a socket, read a credential, insert a job, or schedule a timer.
"""

from __future__ import annotations

import inspect
from collections.abc import Sequence
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
from money_machine.assets.portfolio_eligibility import (
    ExperimentBatch,
    ListingCandidate,
    PortfolioResult,
    QueuedExperiment,
    SnapshotView,
    counts_as_cull,
    evaluate_portfolio,
    is_job_type,
    is_portfolio_decision,
    is_successful_result,
    schedule_new_front,
)
from money_machine.domain.enums import DecisionType
from money_machine.domain.events import EventName
from money_machine.domain.models.common import EvidenceReference

METRICS_EVIDENCE_KEY = "metrics_fixture_implemented"
MATURITY_EVIDENCE_KEY = "maturity_clock_implemented"
PORTFOLIO_EVIDENCE_KEY = "portfolio_eligibility_implemented"
EARNED_EVIDENCE_KEYS = frozenset(
    {METRICS_EVIDENCE_KEY, MATURITY_EVIDENCE_KEY, PORTFOLIO_EVIDENCE_KEY}
)
_DECIDED = datetime(2026, 10, 16, tzinfo=UTC)
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
    """Return the earned Session 10 keys. A miss raises instead of returning them."""
    _prove_metrics()
    _prove_maturity()
    _prove_portfolio()
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


def _portfolio_id(number: int) -> UUID:
    return UUID(int=number)


def _candidate(
    number: int,
    *,
    shop: int = 1,
    live_days: int = 30,
    in_window: bool = True,
    views: int = 0,
    favourites: int = 0,
    orders: int = 0,
    revenue: int = 0,
) -> ListingCandidate:
    return ListingCandidate(
        listing_id=_portfolio_id(1_000 + number),
        product_id=_portfolio_id(2_000 + number),
        spec_id=_portfolio_id(3_000 + number),
        workflow_id=_portfolio_id(4_000 + number),
        shop_id=_portfolio_id(shop),
        live_days=live_days,
        in_window=in_window,
        has_defect=False,
        snapshot=SnapshotView(
            snapshot_id=_portfolio_id(5_000 + number),
            views=views,
            favourites=favourites,
            orders=orders,
            gross_revenue=revenue,
            reconciled=True,
        ),
    )


def _cull_listing_ids(results: Sequence[PortfolioResult]) -> set[UUID]:
    return {item.listing_id for item in results if item.decision is DecisionType.CULL}


def _prove_portfolio() -> None:
    percent = inspect.signature(evaluate_portfolio).parameters["cull_bottom_percent"]
    if percent.default != "80":
        raise Session10ProofError("portfolio_percent")
    for label in ("TOO_YOUNG", "CULL_CANDIDATE", "MULTIPLY_CANDIDATE"):
        if is_portfolio_decision(label):
            raise Session10ProofError("portfolio_label")
    for decision in DecisionType:
        if not is_portfolio_decision(decision.value):
            raise Session10ProofError("portfolio_label")
    young = evaluate_portfolio((_candidate(1, live_days=29, views=12),), decided_at=_DECIDED)
    if young:
        raise Session10ProofError("portfolio_young")
    small = tuple(_candidate(10 + offset, orders=offset + 1, views=5) for offset in range(4))
    if _cull_listing_ids(evaluate_portfolio(small, decided_at=_DECIDED)):
        raise Session10ProofError("portfolio_small")
    identical = tuple(
        _candidate(70 + offset, shop=3, orders=4, views=4, favourites=4, revenue=4)
        for offset in range(10)
    )
    if _cull_listing_ids(evaluate_portfolio(identical, decided_at=_DECIDED)):
        raise Session10ProofError("portfolio_identical")
    worst = _candidate(50, orders=1, views=6, favourites=1, revenue=1)
    peers = tuple(
        _candidate(51 + offset, orders=5, views=6, favourites=1, revenue=5) for offset in range(4)
    )
    ranked = evaluate_portfolio((worst, *peers), decided_at=_DECIDED)
    found = {item.listing_id: item for item in ranked}
    cull = found.get(worst.listing_id)
    snapshot = worst.snapshot
    if (
        cull is None
        or snapshot is None
        or cull.decision is not DecisionType.CULL
        or cull.snapshot_id != snapshot.snapshot_id
        or cull.deactivation_job_id is None
        or cull.deactivation_executed
        or EventName.LISTING_CULLED in cull.event_names
        or not counts_as_cull(cull.decision, cull.deactivation_job_id)
        or counts_as_cull(DecisionType.CULL, None)
    ):
        raise Session10ProofError("portfolio_cull")
    low = _candidate(60, orders=1, views=7, favourites=1, revenue=1)
    next_low = _candidate(61, orders=2, views=7, favourites=1, revenue=2)
    tied_left = _candidate(62, orders=4, views=7, favourites=1, revenue=4)
    tied_right = _candidate(63, orders=4, views=7, favourites=1, revenue=4)
    best = _candidate(64, orders=9, views=7, favourites=1, revenue=9)
    tied = {
        item.listing_id: item
        for item in evaluate_portfolio(
            (low, next_low, tied_left, tied_right, best),
            decided_at=_DECIDED,
        )
    }
    marked = tied.get(low.listing_id)
    left = tied.get(tied_left.listing_id)
    right = tied.get(tied_right.listing_id)
    if (
        marked is None
        or marked.decision is not DecisionType.CULL
        or left is None
        or right is None
        or left.decision is DecisionType.CULL
        or right.decision is DecisionType.CULL
    ):
        raise Session10ProofError("portfolio_tie")
    winner = _candidate(110, orders=4, views=20, favourites=2, revenue=4)
    multiplied = evaluate_portfolio((winner,), decided_at=_DECIDED)
    if len(multiplied) != 1 or not is_successful_result(multiplied[0]):
        raise Session10ProofError("portfolio_multiply")
    successor = multiplied[0]
    if (
        successor.successor_spec_id == winner.spec_id
        or successor.parent_spec_id != winner.spec_id
        or successor.job_types
        or is_job_type("BUILD_NOTION_TEMPLATE")
        or is_successful_result(("CREATE_SUCCESSOR_SPEC", "CHECK_DEDUPE", "BUILD_NOTION_TEMPLATE"))
    ):
        raise Session10ProofError("portfolio_multiply")
    held = evaluate_portfolio((_candidate(120),), decided_at=_DECIDED)
    if len(held) != 1 or held[0].decision is not DecisionType.HOLD:
        raise Session10ProofError("portfolio_hold")
    nxt = held[0].next_collection_at
    if nxt is None or nxt <= held[0].decided_at or held[0].deactivation_job_id is not None:
        raise Session10ProofError("portfolio_hold")
    if evaluate_portfolio((_candidate(120),), decided_at=_DECIDED + timedelta(days=1), priors=held):
        raise Session10ProofError("portfolio_hold")
    quiet = evaluate_portfolio((_candidate(90, views=25, favourites=3),), decided_at=_DECIDED)
    if (
        len(quiet) != 1
        or quiet[0].decision is not DecisionType.REPAIR
        or quiet[0].repair_job_id is None
        or quiet[0].deactivation_job_id is not None
        or EventName.REPAIR_COMPLETED in quiet[0].event_names
    ):
        raise Session10ProofError("portfolio_repair")
    blocked = QueuedExperiment(
        experiment_id=_portfolio_id(8001),
        product_id=_portfolio_id(8002),
        state="QUEUED",
        blocked=True,
        variant_of_winner=False,
    )
    eligible = QueuedExperiment(
        experiment_id=_portfolio_id(8005),
        product_id=_portfolio_id(8006),
        state="QUEUED",
        blocked=False,
        variant_of_winner=False,
    )
    slot = schedule_new_front(
        ExperimentBatch(
            batch_id=_portfolio_id(8007),
            winner_product_id=_portfolio_id(8000),
            experiments=(blocked, eligible),
            publishing_enabled=False,
        )
    )
    blocked_outcome = next(
        item for item in slot.outcomes if item.experiment_id == blocked.experiment_id
    )
    if (
        slot.scheduled_experiment_ids != (eligible.experiment_id,)
        or slot.publication_ids
        or blocked_outcome.state != "QUEUED"
        or blocked_outcome.delivered
    ):
        raise Session10ProofError("portfolio_slot")
    source = Path(evaluate_portfolio.__code__.co_filename).read_text(encoding="utf-8")
    if "deactivate_listing" in source or "httpx" in source:
        raise Session10ProofError("portfolio_live")
