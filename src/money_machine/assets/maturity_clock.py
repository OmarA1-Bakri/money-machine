"""Count thirty accumulated live UTC periods. Paused time does not count.

Maturity is ``MATURITY_LIVE_DAYS`` complete ACTIVE periods of 24 hours after
the verified publication time. Inactive intervals and leftover hours are
excluded. A stored ``live_days`` value is not evidence. A defect inside the
window returns repair data immediately. The due result names a stable
idempotency key for the listing and the accumulated-live rule.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

ACCUMULATED_LIVE_RULE = "accumulated-live-periods"
MATURITY_LIVE_DAYS = 30
_PERIOD_SECONDS = 24 * 60 * 60


@dataclass(frozen=True, slots=True)
class LiveInterval:
    """One contiguous ACTIVE or INACTIVE stretch, in timezone-aware UTC."""

    status: Literal["ACTIVE", "INACTIVE"]
    started_at: datetime
    ended_at: datetime


@dataclass(frozen=True, slots=True)
class ListingDefect:
    """A defect observed while the listing is still inside the live window."""

    code: str
    detected_at: datetime


@dataclass(frozen=True, slots=True)
class RepairWork:
    """Repair work as data. This value is not a job row."""

    repair_job_id: UUID
    listing_id: UUID
    defect_code: str
    detected_at: datetime


@dataclass(frozen=True, slots=True)
class MaturityEvaluation:
    """Accumulated live periods and whether a portfolio decision is due."""

    accumulated_live_periods: int
    mature: bool
    portfolio_decision_due: bool
    repair: RepairWork | None
    idempotency_key: str | None


def repair_work_id(listing_id: UUID, defect_code: str) -> UUID:
    """Stable id for repair data. The same listing and defect name the same id."""
    return uuid5(NAMESPACE_URL, f"money-machine:repair-work:{listing_id}:{defect_code}")


def evaluate_maturity(
    *,
    listing_id: UUID,
    published_at: datetime,
    intervals: Sequence[LiveInterval],
    evaluated_at: datetime,
    live_days: int | None = None,
    defect: ListingDefect | None = None,
) -> MaturityEvaluation:
    """Return accumulated live periods, repair data, or a due portfolio key.

    ``live_days`` is accepted and ignored. Intervals are the only evidence.
    """
    del live_days
    published = _as_utc("published_at", published_at)
    evaluated = _as_utc("evaluated_at", evaluated_at)
    periods = _accumulated_live_periods(published, intervals, evaluated)
    repair = _repair(listing_id, defect, published, evaluated)
    mature = periods >= MATURITY_LIVE_DAYS
    decision_due = mature and repair is None
    key = f"{listing_id}:{ACCUMULATED_LIVE_RULE}:{MATURITY_LIVE_DAYS}" if decision_due else None
    return MaturityEvaluation(
        accumulated_live_periods=periods,
        mature=mature,
        portfolio_decision_due=decision_due,
        repair=repair,
        idempotency_key=key,
    )


def _as_utc(label: str, value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be a timezone-aware UTC datetime")
    return value.astimezone(UTC)


def _accumulated_live_periods(
    published_at: datetime,
    intervals: Sequence[LiveInterval],
    evaluated_at: datetime,
) -> int:
    ranges: list[tuple[datetime, datetime]] = []
    for interval in intervals:
        start = _as_utc("interval.started_at", interval.started_at)
        end = _as_utc("interval.ended_at", interval.ended_at)
        if end < start:
            raise ValueError("interval ends before it starts")
        if interval.status == "INACTIVE":
            continue
        if interval.status != "ACTIVE":
            raise ValueError(f"unknown interval status: {interval.status}")
        clipped_start = max(start, published_at)
        clipped_end = min(end, evaluated_at)
        if clipped_end > clipped_start:
            ranges.append((clipped_start, clipped_end))
    ranges.sort(key=lambda item: item[0])
    total_seconds = 0
    previous_end: datetime | None = None
    for start, end in ranges:
        if previous_end is not None and start < previous_end:
            raise ValueError("active intervals overlap")
        delta = end - start
        total_seconds += delta.days * _PERIOD_SECONDS + delta.seconds
        previous_end = end
    return total_seconds // _PERIOD_SECONDS


def _repair(
    listing_id: UUID,
    defect: ListingDefect | None,
    published_at: datetime,
    evaluated_at: datetime,
) -> RepairWork | None:
    if defect is None:
        return None
    detected_at = _as_utc("defect.detected_at", defect.detected_at)
    if detected_at < published_at or detected_at > evaluated_at:
        return None
    return RepairWork(
        repair_job_id=repair_work_id(listing_id, defect.code),
        listing_id=listing_id,
        defect_code=defect.code,
        detected_at=detected_at,
    )
