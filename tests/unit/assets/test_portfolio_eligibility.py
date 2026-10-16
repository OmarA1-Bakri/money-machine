"""Level 1 pins for in-memory cull and multiply eligibility."""

from __future__ import annotations

import inspect
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID

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

_WHEN = datetime(2026, 10, 16, tzinfo=UTC)
_DECISIONS = {
    DecisionType.HOLD,
    DecisionType.REPAIR,
    DecisionType.CULL,
    DecisionType.MULTIPLY,
}


def _uuid(number: int) -> UUID:
    return UUID(int=number)


def _listing(
    number: int,
    *,
    shop: int = 1,
    live_days: int = 30,
    in_window: bool = True,
    defect: bool = False,
    views: int = 0,
    favourites: int = 0,
    orders: int = 0,
    revenue: int = 0,
    reconciled: bool = True,
    snapshot_number: int | None = None,
) -> ListingCandidate:
    return ListingCandidate(
        listing_id=_uuid(1_000 + number),
        product_id=_uuid(2_000 + number),
        spec_id=_uuid(3_000 + number),
        workflow_id=_uuid(4_000 + number),
        shop_id=_uuid(shop),
        live_days=live_days,
        in_window=in_window,
        has_defect=defect,
        snapshot=SnapshotView(
            snapshot_id=_uuid(5_000 + (snapshot_number if snapshot_number is not None else number)),
            views=views,
            favourites=favourites,
            orders=orders,
            gross_revenue=revenue,
            reconciled=reconciled,
        ),
    )


def _by_id(results: Sequence[PortfolioResult]) -> dict[UUID, PortfolioResult]:
    return {result.listing_id: result for result in results}


def _cull_ids(results: Sequence[PortfolioResult]) -> set[UUID]:
    return {result.listing_id for result in results if result.decision is DecisionType.CULL}


def test_young_listing_has_no_decision_until_a_reconciled_mature_verdict() -> None:
    young = _listing(1, live_days=29, views=12, orders=0)
    assert evaluate_portfolio([young], decided_at=_WHEN) == ()

    for label in ("TOO_YOUNG", "CULL_CANDIDATE", "MULTIPLY_CANDIDATE"):
        assert is_portfolio_decision(label) is False
    for decision in _DECISIONS:
        assert is_portfolio_decision(decision.value) is True

    mature = evaluate_portfolio([_listing(2, live_days=30)], decided_at=_WHEN)
    assert len(mature) == 1
    assert mature[0].decision in _DECISIONS
    assert mature[0].decision is DecisionType.HOLD

    defect = evaluate_portfolio(
        [_listing(3, live_days=10, defect=True, views=4, orders=1)],
        decided_at=_WHEN,
    )
    assert len(defect) == 1
    assert defect[0].decision is DecisionType.REPAIR

    unreconciled = _listing(4, live_days=40, views=30, orders=3, reconciled=False)
    assert evaluate_portfolio([unreconciled], decided_at=_WHEN) == ()
    assert (
        evaluate_portfolio(
            [_listing(5, live_days=5, defect=True, reconciled=False)],
            decided_at=_WHEN,
        )
        == ()
    )


def test_cull_pool_keeps_small_cohorts_ties_and_the_percent_string() -> None:
    parameter = inspect.signature(evaluate_portfolio).parameters["cull_bottom_percent"]
    assert parameter.default == "80"
    assert isinstance(parameter.default, str)

    for size in (1, 2, 3, 4):
        rows = [_listing(10 * size + offset, orders=offset + 1, views=5) for offset in range(size)]
        assert _cull_ids(evaluate_portfolio(rows, decided_at=_WHEN)) == set()

    locals_only = [
        _listing(30 + offset, shop=7, orders=10, views=8, favourites=2, revenue=10)
        for offset in range(4)
    ]
    other_shop = _listing(40, shop=8, orders=1, views=8, favourites=2, revenue=1)
    outside = _listing(41, shop=7, orders=1, views=8, favourites=2, revenue=1, in_window=False)
    mixed = [*locals_only, other_shop, outside]
    before = [row.listing_id for row in mixed]
    assert _cull_ids(evaluate_portfolio(mixed, decided_at=_WHEN)) == set()
    assert [row.listing_id for row in mixed] == before

    worst = _listing(50, orders=1, views=6, favourites=1, revenue=1)
    peers = [
        _listing(51 + offset, orders=5, views=6, favourites=1, revenue=5) for offset in range(4)
    ]
    marked = _cull_ids(evaluate_portfolio([worst, *peers], decided_at=_WHEN))
    assert marked == {worst.listing_id}

    low = _listing(60, orders=1, views=7, favourites=1, revenue=1)
    next_low = _listing(61, orders=2, views=7, favourites=1, revenue=2)
    tied_left = _listing(62, orders=4, views=7, favourites=1, revenue=4)
    tied_right = _listing(63, orders=4, views=7, favourites=1, revenue=4)
    best = _listing(64, orders=9, views=7, favourites=1, revenue=9)
    tied = _by_id(
        evaluate_portfolio(
            [low, next_low, tied_left, tied_right, best],
            decided_at=_WHEN,
        )
    )
    assert tied[low.listing_id].decision is DecisionType.CULL
    assert tied[next_low.listing_id].decision is DecisionType.CULL
    assert tied[tied_left.listing_id].decision is not DecisionType.CULL
    assert tied[tied_right.listing_id].decision is not DecisionType.CULL

    identical = [
        _listing(70 + offset, shop=3, orders=4, views=4, favourites=4, revenue=4)
        for offset in range(10)
    ]
    assert _cull_ids(evaluate_portfolio(identical, decided_at=_WHEN)) == set()

    distinct = [
        _listing(80 + offset, shop=4, orders=offset + 1, views=3, favourites=1, revenue=offset + 1)
        for offset in range(10)
    ]
    ranked = _by_id(evaluate_portfolio(distinct, decided_at=_WHEN))
    assert ranked[distinct[8].listing_id].decision is not DecisionType.CULL
    assert ranked[distinct[9].listing_id].decision is not DecisionType.CULL
    assert len(_cull_ids(tuple(ranked.values()))) != 8

    quiet = _listing(90, views=25, orders=0, favourites=3)
    repaired = evaluate_portfolio([quiet], decided_at=_WHEN)
    assert len(repaired) == 1
    assert repaired[0].decision is DecisionType.REPAIR
    assert repaired[0].deactivation_job_id is None

    immature = _listing(91, live_days=11, orders=0, views=1)
    mature_bottom = _listing(92, orders=1, views=6, favourites=1, revenue=1)
    mature_peers = [
        _listing(93 + offset, orders=5, views=6, favourites=1, revenue=5) for offset in range(4)
    ]
    ranked_with_immature = _cull_ids(
        evaluate_portfolio([immature, mature_bottom, *mature_peers], decided_at=_WHEN)
    )
    assert immature.listing_id not in ranked_with_immature
    assert mature_bottom.listing_id in ranked_with_immature


def test_cull_cites_reconciled_snapshot_without_listing_culled() -> None:
    worst = _listing(100, orders=1, views=9, favourites=1, revenue=1)
    peers = [
        _listing(101 + offset, orders=6, views=9, favourites=1, revenue=6) for offset in range(4)
    ]
    found = _by_id(evaluate_portfolio([worst, *peers], decided_at=_WHEN))
    cull = found[worst.listing_id]
    assert worst.snapshot is not None
    assert worst.snapshot.reconciled is True
    assert cull.decision is DecisionType.CULL
    assert cull.snapshot_id == worst.snapshot.snapshot_id
    assert cull.deactivation_job_id is not None
    assert cull.deactivation_executed is False
    assert EventName.LISTING_CULLED not in cull.event_names
    assert counts_as_cull(DecisionType.CULL, None) is False
    assert counts_as_cull(cull.decision, cull.deactivation_job_id) is True


def test_multiply_returns_a_successor_and_stops_at_dedupe() -> None:
    winner = _listing(110, orders=4, views=20, favourites=2, revenue=4)
    original_spec = winner.spec_id
    original_product = winner.product_id
    original_workflow = winner.workflow_id
    results = evaluate_portfolio([winner], decided_at=_WHEN)
    assert len(results) == 1
    result = results[0]
    assert result.decision is DecisionType.MULTIPLY
    assert result.successor_spec_id is not None
    assert result.successor_spec_id != original_spec
    assert result.lineage_kind == "SUCCESSOR"
    assert result.successor_workflow_id is not None
    assert result.successor_workflow_id != original_workflow
    assert result.parent_spec_id == original_spec
    assert result.parent_product_id == original_product
    assert result.parent_decision_id == result.decision_id
    assert result.parent_workflow_id == original_workflow
    assert winner.spec_id == original_spec
    assert winner.product_id == original_product
    assert winner.workflow_id == original_workflow
    assert result.build_step is None
    assert result.stops_at == "DEDUPE_CHECK"
    labels = ("CREATE_SUCCESSOR_SPEC", "CHECK_DEDUPE", "BUILD_NOTION_TEMPLATE")
    assert result.job_types == ()
    for label in labels:
        assert is_job_type(label) is False
        assert label not in result.job_types
    assert is_successful_result(labels) is False
    assert is_successful_result(result) is True


def test_hold_names_a_future_collection_and_suppresses_an_early_repeat() -> None:
    listing = _listing(120)
    first = evaluate_portfolio([listing], decided_at=_WHEN)
    assert len(first) == 1
    hold = first[0]
    assert hold.decision is DecisionType.HOLD
    assert hold.next_collection_at is not None
    assert hold.next_collection_at > hold.decided_at
    assert hold.deactivation_job_id is None
    assert hold.successor_spec_id is None
    early = hold.decided_at + timedelta(days=1)
    assert early < hold.next_collection_at
    assert evaluate_portfolio([listing], decided_at=early, priors=first) == ()


def test_repair_waits_for_a_new_reconciled_snapshot() -> None:
    listing = _listing(130, views=18, orders=0, favourites=2)
    first = evaluate_portfolio([listing], decided_at=_WHEN)
    assert len(first) == 1
    repair = first[0]
    assert repair.decision is DecisionType.REPAIR
    assert repair.repair_job_id is not None
    assert repair.deactivation_job_id is None
    assert EventName.REPAIR_COMPLETED not in repair.event_names
    assert evaluate_portfolio([listing], decided_at=_WHEN + timedelta(days=1), priors=first) == ()

    assert listing.snapshot is not None
    unreconciled = replace(
        listing,
        snapshot=replace(listing.snapshot, snapshot_id=_uuid(5_999), reconciled=False),
    )
    assert (
        evaluate_portfolio(
            [unreconciled],
            decided_at=_WHEN + timedelta(days=2),
            priors=first,
        )
        == ()
    )
    fresh = replace(
        listing,
        snapshot=replace(listing.snapshot, snapshot_id=_uuid(5_998)),
    )
    second = evaluate_portfolio([fresh], decided_at=_WHEN + timedelta(days=3), priors=first)
    assert len(second) == 1
    assert second[0].decision is DecisionType.REPAIR
    assert second[0].snapshot_id == _uuid(5_998)


def test_batch_schedules_one_new_front_and_publishes_nothing() -> None:
    winner_product = _uuid(8_000)
    blocked = QueuedExperiment(
        experiment_id=_uuid(8_001),
        product_id=_uuid(8_002),
        state="QUEUED",
        blocked=True,
        variant_of_winner=False,
    )
    variant = QueuedExperiment(
        experiment_id=_uuid(8_003),
        product_id=_uuid(8_004),
        state="QUEUED",
        blocked=False,
        variant_of_winner=True,
    )
    eligible = QueuedExperiment(
        experiment_id=_uuid(8_005),
        product_id=_uuid(8_006),
        state="QUEUED",
        blocked=False,
        variant_of_winner=False,
    )
    batch = ExperimentBatch(
        batch_id=_uuid(8_007),
        winner_product_id=winner_product,
        experiments=(blocked, variant, eligible),
        publishing_enabled=False,
    )
    assert batch.experiments
    slot = schedule_new_front(batch)
    assert slot.scheduled_experiment_ids == (eligible.experiment_id,)
    outcomes = {item.experiment_id: item for item in slot.outcomes}
    assert outcomes[blocked.experiment_id].state == "QUEUED"
    assert outcomes[blocked.experiment_id].delivered is False
    assert blocked.experiment_id not in slot.delivered_experiment_ids
    assert outcomes[variant.experiment_id].state == "QUEUED"
    assert variant.experiment_id not in slot.scheduled_experiment_ids
    assert slot.publication_ids == ()
