"""Map an injected metrics fixture into one domain snapshot and a pure loop plan.

Weekly totals are summed from those snapshots. The plan records name work to do.
They do not insert jobs, and they do not keep a second copy of the metric fields.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from money_machine.domain.events import EventName
from money_machine.domain.models.common import EffectReference, EvidenceReference
from money_machine.domain.models.portfolio import MetricsSnapshot

_ROW_FIELDS = frozenset(
    {
        "snapshot_id",
        "listing_id",
        "listing_version",
        "provider",
        "observed_at",
        "views",
        "favourites",
        "orders",
        "gross_revenue",
        "currency",
        "reconciled",
        "window_start",
        "window_end",
        "evidence",
    }
)
_CUMULATIVE_FIELDS = frozenset(
    {
        "cumulative_views",
        "cumulative_favourites",
        "cumulative_orders",
        "cumulative_sales",
    }
)
_CULL_OPERATION = "CULL"
_MONTHLY_CADENCE: Literal["monthly"] = "monthly"
_MONTHLY_JOBS: tuple[tuple[str, Literal["research", "build-slot", "scale"]], ...] = (
    ("ResearchCollectionJob", "research"),
    ("BuildSlotJob", "build-slot"),
    ("ScaleEvaluationJob", "scale"),
)
_WindowKey = tuple[UUID, int, datetime, datetime]


class MetricsFixtureRefusal(ValueError):
    """The fixture cannot become a snapshot or a loop plan."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class FixtureObservation:
    """Window key for one domain snapshot. Counts live only on ``snapshot``."""

    window_start: datetime
    window_end: datetime
    snapshot: MetricsSnapshot


@dataclass(frozen=True, slots=True)
class CumulativeTotals:
    """Views and orders summed from weekly snapshots."""

    views: int
    orders: int


@dataclass(frozen=True, slots=True)
class ActiveListing:
    """One listing the weekly plan may collect."""

    listing_id: UUID
    listing_version: int
    active: bool


@dataclass(frozen=True, slots=True)
class CollectionRecord:
    """One pure collection or shop-review step for a window."""

    kind: Literal["collection", "shop_review"]
    window_start: datetime
    window_end: datetime
    listing_id: UUID | None
    listing_version: int | None


@dataclass(frozen=True, slots=True)
class WeeklyPlan:
    """New records for a window, plus the snapshot objects that were supplied."""

    records: tuple[CollectionRecord, ...]
    prior_snapshots: tuple[MetricsSnapshot, ...]


@dataclass(frozen=True, slots=True)
class PlannedJob:
    """One monthly job named as data, with no inserted status."""

    job_type: str
    role: Literal["research", "build-slot", "scale"]
    shop_id: UUID
    window_start: datetime
    window_end: datetime
    admitted_event: EventName


@dataclass(frozen=True, slots=True)
class MonthlyRecord:
    """A month-due deep pass and the three jobs it names."""

    cadence: Literal["monthly"]
    window_start: datetime
    window_end: datetime
    jobs: tuple[PlannedJob, ...]


@dataclass(frozen=True, slots=True)
class MilestoneInput:
    """Source rows a milestone report is allowed to read."""

    effects: tuple[EffectReference, ...]
    successor_spec_id: UUID | None
    measured: bool
    operator_minutes: int | None


@dataclass(frozen=True, slots=True)
class MilestoneReport:
    """Milestones copied from source rows. An unmeasured total stays unset."""

    first_cull: EffectReference | None
    first_multiplied_winner: UUID | None
    operator_minutes: int | None


def snapshots_from_fixture(
    rows: Sequence[Mapping[str, object]],
) -> tuple[FixtureObservation, ...]:
    """Build one domain snapshot per listing version and window."""
    seen: set[_WindowKey] = set()
    loaded: list[FixtureObservation] = []
    for row in rows:
        observation = _observation(row)
        key = (
            observation.snapshot.listing_id,
            observation.snapshot.listing_version,
            observation.window_start,
            observation.window_end,
        )
        if key in seen:
            raise MetricsFixtureRefusal("duplicate_listing_window")
        seen.add(key)
        loaded.append(observation)
    return tuple(loaded)


def cumulative_totals(snapshots: Sequence[MetricsSnapshot]) -> CumulativeTotals:
    """Sum weekly views and orders. The sums are not stored on the snapshots."""
    return CumulativeTotals(
        views=sum(snapshot.views for snapshot in snapshots),
        orders=sum(snapshot.orders for snapshot in snapshots),
    )


def plan_weekly(
    listings: Sequence[ActiveListing],
    *,
    window_start: datetime,
    window_end: datetime,
    prior_snapshots: Sequence[MetricsSnapshot],
    existing_records: Sequence[CollectionRecord] = (),
) -> WeeklyPlan:
    """Plan one collection per active listing, then one shop review.

    A window that already has records contributes nothing new. The snapshot
    objects passed in are returned unchanged.
    """
    start, end = _window(window_start, window_end)
    snapshots = tuple(prior_snapshots)
    if any(
        record.window_start == start and record.window_end == end for record in existing_records
    ):
        return WeeklyPlan(records=(), prior_snapshots=snapshots)
    records = [
        CollectionRecord(
            kind="collection",
            window_start=start,
            window_end=end,
            listing_id=listing.listing_id,
            listing_version=listing.listing_version,
        )
        for listing in listings
        if listing.active
    ]
    records.append(
        CollectionRecord(
            kind="shop_review",
            window_start=start,
            window_end=end,
            listing_id=None,
            listing_version=None,
        )
    )
    return WeeklyPlan(records=tuple(records), prior_snapshots=snapshots)


def plan_monthly(
    *,
    cadence: str,
    weekly_fire_count: int,
    month_due: bool,
    window_start: datetime,
    window_end: datetime,
    shop_id: UUID,
) -> MonthlyRecord | None:
    """Plan the monthly deep pass when the cadence says the month is due.

    ``weekly_fire_count`` does not create the record. A fourth weekly fire
    with ``month_due`` false returns no monthly record.
    """
    if weekly_fire_count < 0:
        raise MetricsFixtureRefusal("weekly_fire_count")
    if cadence != _MONTHLY_CADENCE:
        raise MetricsFixtureRefusal("cadence")
    if not month_due:
        return None
    start, end = _window(window_start, window_end)
    jobs = tuple(
        PlannedJob(
            job_type=job_type,
            role=role,
            shop_id=shop_id,
            window_start=start,
            window_end=end,
            admitted_event=EventName.MONTHLY_REVIEW_COMPLETED,
        )
        for job_type, role in _MONTHLY_JOBS
    )
    return MonthlyRecord(
        cadence=_MONTHLY_CADENCE,
        window_start=start,
        window_end=end,
        jobs=jobs,
    )


def derive_milestones(fixture: MilestoneInput) -> MilestoneReport:
    """Read milestones from effects and a successor spec id.

    Operator minutes are kept only when the fixture says they were measured.
    """
    if fixture.measured:
        if fixture.operator_minutes is None or fixture.operator_minutes < 0:
            raise MetricsFixtureRefusal("operator_minutes")
        minutes: int | None = fixture.operator_minutes
    elif fixture.operator_minutes is not None:
        raise MetricsFixtureRefusal("unmeasured_operator_minutes")
    else:
        minutes = None
    cull = next(
        (
            effect
            for effect in fixture.effects
            if effect.operation == _CULL_OPERATION and effect.effect_state == "CONFIRMED"
        ),
        None,
    )
    return MilestoneReport(
        first_cull=cull,
        first_multiplied_winner=fixture.successor_spec_id,
        operator_minutes=minutes,
    )


def _observation(row: Mapping[str, object]) -> FixtureObservation:
    extra = frozenset(row) - _ROW_FIELDS
    if extra & _CUMULATIVE_FIELDS:
        raise MetricsFixtureRefusal("cumulative_not_writable")
    if extra:
        raise MetricsFixtureRefusal("extra_provider_stat")
    missing = _ROW_FIELDS - frozenset(row)
    if missing:
        raise MetricsFixtureRefusal("missing_field")
    start, end = _window(
        _moment(row["window_start"], "window"), _moment(row["window_end"], "window")
    )
    evidence = row["evidence"]
    if not isinstance(evidence, EvidenceReference):
        raise MetricsFixtureRefusal("evidence")
    snapshot = MetricsSnapshot(
        snapshot_id=_uuid(row["snapshot_id"], "snapshot_id"),
        listing_id=_uuid(row["listing_id"], "listing_id"),
        listing_version=_count(row["listing_version"], "listing_version"),
        provider=_text(row["provider"], "provider"),
        observed_at=_moment(row["observed_at"], "observed_at"),
        views=_count(row["views"], "views"),
        favourites=_count(row["favourites"], "favourites"),
        orders=_count(row["orders"], "orders"),
        gross_revenue=_money(row["gross_revenue"]),
        currency=_text(row["currency"], "currency"),
        reconciled=_flag(row["reconciled"], "reconciled"),
        source_evidence=(evidence,),
    )
    return FixtureObservation(window_start=start, window_end=end, snapshot=snapshot)


def _window(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    if end <= start:
        raise MetricsFixtureRefusal("window")
    return start, end


def _moment(value: object, code: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise MetricsFixtureRefusal(code)
    return value.astimezone(UTC)


def _uuid(value: object, code: str) -> UUID:
    if not isinstance(value, UUID):
        raise MetricsFixtureRefusal(code)
    return value


def _text(value: object, code: str) -> str:
    if not isinstance(value, str):
        raise MetricsFixtureRefusal(code)
    return value


def _count(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MetricsFixtureRefusal(code)
    return value


def _flag(value: object, code: str) -> bool:
    if not isinstance(value, bool):
        raise MetricsFixtureRefusal(code)
    return value


def _money(value: object) -> Decimal:
    if not isinstance(value, Decimal):
        raise MetricsFixtureRefusal("gross_revenue")
    return value
