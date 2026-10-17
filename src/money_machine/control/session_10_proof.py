"""Earn the Session 10 metrics key from the injected fixture.

The proof does not open a socket, read a credential, or insert a job.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

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
EARNED_EVIDENCE_KEYS = frozenset({METRICS_EVIDENCE_KEY})
_START = datetime(2026, 10, 5, tzinfo=UTC)
_END = datetime(2026, 10, 12, tzinfo=UTC)
_OBSERVED = datetime(2026, 10, 12, 9, tzinfo=UTC)


class Session10ProofError(ValueError):
    """The Session 10 fixture did not earn its evidence key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def prove_session_10() -> frozenset[str]:
    """Return the metrics key. A miss raises instead of returning it."""
    _prove_metrics()
    return EARNED_EVIDENCE_KEYS


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
