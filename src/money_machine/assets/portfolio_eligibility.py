"""In-memory portfolio eligibility. No provider call and no persisted row.

Decisions are only ``HOLD``, ``REPAIR``, ``CULL``, and ``MULTIPLY``. The
bottom-percent value is a cohort pool: listings strictly worse than the
cutoff can be marked, ties on that score stay out, and cohorts under five
are not percentile-eligible. ``CULL`` names an unexecuted deactivation.
``MULTIPLY`` names a successor and stops at dedupe.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, assert_never
from uuid import UUID, uuid5

from money_machine.domain.enums import DecisionType
from money_machine.domain.events import EventName

_NAMESPACE = UUID("4f6a0b1c-8d2e-4a70-9c11-6b5d4e3f2a10")
_MATURITY_LIVE_DAYS = 30
_MIN_COHORT = 5
_COLLECTION_GAP = timedelta(days=7)
_NOT_JOB_TYPES = frozenset(
    {
        "CREATE_SUCCESSOR_SPEC",
        "CHECK_DEDUPE",
        "BUILD_NOTION_TEMPLATE",
    }
)

type _Score = tuple[int, int, int, int]
type ExperimentState = Literal["QUEUED", "RUNNING", "CONCLUDED", "ABANDONED"]
type OutcomeState = Literal["QUEUED", "SCHEDULED", "RUNNING", "CONCLUDED", "ABANDONED"]


@dataclass(frozen=True, slots=True)
class SnapshotView:
    """Reconciled metrics cited by a decision. Revenue is minor units."""

    snapshot_id: UUID
    views: int
    favourites: int
    orders: int
    gross_revenue: int
    reconciled: bool


@dataclass(frozen=True, slots=True)
class ListingCandidate:
    """One listing inside or outside the shop evaluation window."""

    listing_id: UUID
    product_id: UUID
    spec_id: UUID
    workflow_id: UUID
    shop_id: UUID
    live_days: int
    in_window: bool
    has_defect: bool
    snapshot: SnapshotView | None


@dataclass(frozen=True, slots=True)
class PortfolioResult:
    """One in-memory decision. Parent ids are copies, not rewritten rows."""

    listing_id: UUID
    decision_id: UUID
    decision: DecisionType
    decided_at: datetime
    snapshot_id: UUID
    event_names: tuple[EventName, ...]
    deactivation_job_id: UUID | None = None
    deactivation_executed: bool = False
    repair_job_id: UUID | None = None
    next_collection_at: datetime | None = None
    successor_spec_id: UUID | None = None
    lineage_kind: Literal["SUCCESSOR"] | None = None
    successor_workflow_id: UUID | None = None
    parent_spec_id: UUID | None = None
    parent_product_id: UUID | None = None
    parent_decision_id: UUID | None = None
    parent_workflow_id: UUID | None = None
    build_step: None = None
    stops_at: Literal["DEDUPE_CHECK"] | None = None
    job_types: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class QueuedExperiment:
    """A batch experiment that is still waiting for a new-front slot."""

    experiment_id: UUID
    product_id: UUID
    state: ExperimentState
    blocked: bool
    variant_of_winner: bool


@dataclass(frozen=True, slots=True)
class ExperimentBatch:
    """One non-empty build batch and the experiments competing for its slot."""

    batch_id: UUID
    winner_product_id: UUID
    experiments: tuple[QueuedExperiment, ...]
    publishing_enabled: bool


@dataclass(frozen=True, slots=True)
class ExperimentOutcome:
    """The slot's effect on one experiment. Blocked rows stay queued."""

    experiment_id: UUID
    state: OutcomeState
    delivered: bool


@dataclass(frozen=True, slots=True)
class SlotResult:
    """The single scheduled experiment, with publications withheld when disabled."""

    scheduled_experiment_ids: tuple[UUID, ...]
    outcomes: tuple[ExperimentOutcome, ...]
    publication_ids: tuple[UUID, ...]
    delivered_experiment_ids: tuple[UUID, ...]


def is_portfolio_decision(label: str) -> bool:
    """Candidate strings such as ``TOO_YOUNG`` are not decisions."""
    return label in {item.value for item in DecisionType}


def is_job_type(label: str) -> bool:
    """The multiply prompt labels are not job types."""
    return label not in _NOT_JOB_TYPES and label in frozenset[str]()


def counts_as_cull(decision: DecisionType, deactivation_job_id: UUID | None) -> bool:
    """A cull without a deactivation id is not a cull."""
    return decision is DecisionType.CULL and deactivation_job_id is not None


def is_successful_result(value: PortfolioResult | tuple[str, ...]) -> bool:
    """Labels alone are not a successor. A multiply result stops at dedupe."""
    if isinstance(value, tuple):
        return False
    return (
        value.decision is DecisionType.MULTIPLY
        and value.successor_spec_id is not None
        and value.lineage_kind == "SUCCESSOR"
        and value.successor_workflow_id is not None
        and value.parent_workflow_id is not None
        and value.successor_workflow_id != value.parent_workflow_id
        and value.build_step is None
        and value.stops_at == "DEDUPE_CHECK"
    )


def evaluate_portfolio(
    listings: Sequence[ListingCandidate],
    *,
    decided_at: datetime,
    priors: Sequence[PortfolioResult] = (),
    cull_bottom_percent: str = "80",
) -> tuple[PortfolioResult, ...]:
    """Return at most one decision per listing. Omit listings with no decision."""
    if decided_at.tzinfo is None or decided_at.utcoffset() is None:
        raise ValueError("decided_at must be timezone-aware")
    priors_by_listing = {item.listing_id: item for item in priors}
    culled = _cull_ids(listings, cull_bottom_percent)
    multiply = _multiply_ids(listings, culled)
    results: list[PortfolioResult] = []
    for listing in listings:
        snapshot = listing.snapshot
        if snapshot is None or not snapshot.reconciled:
            continue
        if _suppressed(listing, priors_by_listing.get(listing.listing_id), decided_at):
            continue
        decision = _classify(listing, snapshot, culled, multiply)
        if decision is None:
            continue
        results.append(_build(listing, snapshot, decision, decided_at))
    return tuple(results)


def schedule_new_front(batch: ExperimentBatch) -> SlotResult:
    """Schedule one eligible queued experiment. A disabled ramp publishes nothing."""
    scheduled: list[UUID] = []
    outcomes: list[ExperimentOutcome] = []
    for experiment in batch.experiments:
        eligible = _eligible_experiment(experiment, batch.winner_product_id) and not scheduled
        if eligible:
            scheduled.append(experiment.experiment_id)
            outcomes.append(
                ExperimentOutcome(
                    experiment_id=experiment.experiment_id,
                    state="SCHEDULED",
                    delivered=True,
                )
            )
            continue
        outcomes.append(
            ExperimentOutcome(
                experiment_id=experiment.experiment_id,
                state=experiment.state,
                delivered=False,
            )
        )
    scheduled_ids = tuple(scheduled)
    publication_ids = (
        tuple(_derive("publication", experiment_id) for experiment_id in scheduled_ids)
        if batch.publishing_enabled
        else ()
    )
    return SlotResult(
        scheduled_experiment_ids=scheduled_ids,
        outcomes=tuple(outcomes),
        publication_ids=publication_ids,
        delivered_experiment_ids=scheduled_ids,
    )


def _eligible_experiment(experiment: QueuedExperiment, winner_product_id: UUID) -> bool:
    return (
        experiment.state == "QUEUED"
        and not experiment.blocked
        and not experiment.variant_of_winner
        and experiment.product_id != winner_product_id
    )


def _classify(
    listing: ListingCandidate,
    snapshot: SnapshotView,
    culled: frozenset[UUID],
    multiply: frozenset[UUID],
) -> DecisionType | None:
    if listing.has_defect:
        return DecisionType.REPAIR
    if listing.live_days < _MATURITY_LIVE_DAYS:
        return None
    if snapshot.views > 0 and snapshot.orders == 0:
        return DecisionType.REPAIR
    if listing.listing_id in culled:
        return DecisionType.CULL
    if listing.listing_id in multiply:
        return DecisionType.MULTIPLY
    if listing.in_window:
        return DecisionType.HOLD
    return None


def _suppressed(
    listing: ListingCandidate,
    prior: PortfolioResult | None,
    decided_at: datetime,
) -> bool:
    if prior is None:
        return False
    if prior.decision is DecisionType.HOLD:
        next_collection = prior.next_collection_at
        return next_collection is not None and decided_at < next_collection
    if prior.decision is DecisionType.REPAIR:
        snapshot = listing.snapshot
        return snapshot is not None and snapshot.snapshot_id == prior.snapshot_id
    return False


def _build(
    listing: ListingCandidate,
    snapshot: SnapshotView,
    decision: DecisionType,
    decided_at: datetime,
) -> PortfolioResult:
    decision_id = _derive(decision.value, listing.listing_id, snapshot.snapshot_id)
    match decision:
        case DecisionType.HOLD:
            return _record(
                listing,
                snapshot,
                decision,
                decided_at,
                decision_id,
                (EventName.LISTING_HELD,),
                next_collection_at=decided_at + _COLLECTION_GAP,
            )
        case DecisionType.REPAIR:
            return _record(
                listing,
                snapshot,
                decision,
                decided_at,
                decision_id,
                (EventName.LISTING_REPAIR_REQUESTED,),
                repair_job_id=_derive("repair", listing.listing_id, snapshot.snapshot_id),
            )
        case DecisionType.CULL:
            return _record(
                listing,
                snapshot,
                decision,
                decided_at,
                decision_id,
                (EventName.LISTING_CULL_REQUESTED,),
                deactivation_job_id=_derive(
                    "deactivation", listing.listing_id, snapshot.snapshot_id
                ),
                deactivation_executed=False,
            )
        case DecisionType.MULTIPLY:
            return _record(
                listing,
                snapshot,
                decision,
                decided_at,
                decision_id,
                (EventName.WINNER_DETECTED,),
                successor_spec_id=_derive("successor-spec", listing.spec_id, listing.listing_id),
                lineage_kind="SUCCESSOR",
                successor_workflow_id=_derive(
                    "successor-workflow",
                    listing.workflow_id,
                    listing.listing_id,
                ),
                parent_spec_id=listing.spec_id,
                parent_product_id=listing.product_id,
                parent_decision_id=decision_id,
                parent_workflow_id=listing.workflow_id,
                stops_at="DEDUPE_CHECK",
            )
        case _ as unreachable:
            assert_never(unreachable)


def _record(
    listing: ListingCandidate,
    snapshot: SnapshotView,
    decision: DecisionType,
    decided_at: datetime,
    decision_id: UUID,
    event_names: tuple[EventName, ...],
    *,
    deactivation_job_id: UUID | None = None,
    deactivation_executed: bool = False,
    repair_job_id: UUID | None = None,
    next_collection_at: datetime | None = None,
    successor_spec_id: UUID | None = None,
    lineage_kind: Literal["SUCCESSOR"] | None = None,
    successor_workflow_id: UUID | None = None,
    parent_spec_id: UUID | None = None,
    parent_product_id: UUID | None = None,
    parent_decision_id: UUID | None = None,
    parent_workflow_id: UUID | None = None,
    stops_at: Literal["DEDUPE_CHECK"] | None = None,
) -> PortfolioResult:
    return PortfolioResult(
        listing_id=listing.listing_id,
        decision_id=decision_id,
        decision=decision,
        decided_at=decided_at,
        snapshot_id=snapshot.snapshot_id,
        event_names=event_names,
        deactivation_job_id=deactivation_job_id,
        deactivation_executed=deactivation_executed,
        repair_job_id=repair_job_id,
        next_collection_at=next_collection_at,
        successor_spec_id=successor_spec_id,
        lineage_kind=lineage_kind,
        successor_workflow_id=successor_workflow_id,
        parent_spec_id=parent_spec_id,
        parent_product_id=parent_product_id,
        parent_decision_id=parent_decision_id,
        parent_workflow_id=parent_workflow_id,
        build_step=None,
        stops_at=stops_at,
        job_types=(),
    )


def _cull_ids(listings: Sequence[ListingCandidate], cull_bottom_percent: str) -> frozenset[UUID]:
    """Mark listings strictly below the pool cutoff. The percent is not a quota."""
    percent = int(cull_bottom_percent)
    grouped: dict[UUID, list[ListingCandidate]] = {}
    for listing in listings:
        if _in_percentile_cohort(listing):
            grouped.setdefault(listing.shop_id, []).append(listing)
    chosen: set[UUID] = set()
    for group in grouped.values():
        if len(group) < _MIN_COHORT:
            continue
        ordered = sorted(group, key=lambda item: (_score(item), item.listing_id))
        pool = (len(ordered) * percent) // 100
        if pool <= 0:
            continue
        cutoff = _score(ordered[pool - 1])
        for item in ordered:
            if _score(item) < cutoff:
                chosen.add(item.listing_id)
    return frozenset(chosen)


def _multiply_ids(
    listings: Sequence[ListingCandidate],
    culled: frozenset[UUID],
) -> frozenset[UUID]:
    grouped: dict[UUID, list[ListingCandidate]] = {}
    for listing in listings:
        if _in_percentile_cohort(listing):
            grouped.setdefault(listing.shop_id, []).append(listing)
    chosen: set[UUID] = set()
    for group in grouped.values():
        winner = _unique_winner(group)
        if winner is not None and winner not in culled:
            chosen.add(winner)
    return frozenset(chosen)


def _unique_winner(group: Sequence[ListingCandidate]) -> UUID | None:
    ranked = sorted(group, key=lambda item: (_score(item), item.listing_id), reverse=True)
    if not ranked:
        return None
    best = ranked[0]
    snapshot = best.snapshot
    if snapshot is None or snapshot.orders <= 0:
        return None
    if len(ranked) > 1 and _score(ranked[1]) == _score(best):
        return None
    return best.listing_id


def _in_percentile_cohort(listing: ListingCandidate) -> bool:
    snapshot = listing.snapshot
    if snapshot is None or not snapshot.reconciled:
        return False
    if not listing.in_window or listing.has_defect or listing.live_days < _MATURITY_LIVE_DAYS:
        return False
    return not (snapshot.views > 0 and snapshot.orders == 0)


def _score(listing: ListingCandidate) -> _Score:
    snapshot = listing.snapshot
    if snapshot is None:
        return (0, 0, 0, 0)
    return (snapshot.orders, snapshot.gross_revenue, snapshot.favourites, snapshot.views)


def _derive(kind: str, *parts: UUID) -> UUID:
    return uuid5(_NAMESPACE, ":".join((kind, *(str(part) for part in parts))))
