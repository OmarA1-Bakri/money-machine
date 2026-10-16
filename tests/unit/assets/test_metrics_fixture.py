"""Level 1 pins for the injected metrics fixture. No live provider read."""

from __future__ import annotations

import ast
import inspect
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

import pytest

import money_machine.assets.metrics_fixture as metrics_fixture
from money_machine.assets.metrics_fixture import (
    ActiveListing,
    CollectionRecord,
    CumulativeTotals,
    FixtureObservation,
    MetricsFixtureRefusal,
    MilestoneInput,
    MilestoneReport,
    MonthlyRecord,
    PlannedJob,
    WeeklyPlan,
    cumulative_totals,
    derive_milestones,
    plan_monthly,
    plan_weekly,
    snapshots_from_fixture,
)
from money_machine.domain.events import EventName
from money_machine.domain.models.common import EffectReference, EvidenceReference
from money_machine.domain.models.portfolio import MetricsSnapshot

_WHEN = datetime(2026, 10, 12, 9, 0, tzinfo=UTC)
_WEEK = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)
_WEEK_END = datetime(2026, 10, 12, 0, 0, tzinfo=UTC)
_NEXT = datetime(2026, 10, 12, 0, 0, tzinfo=UTC)
_NEXT_END = datetime(2026, 10, 19, 0, 0, tzinfo=UTC)
_LATER = datetime(2026, 10, 19, 0, 0, tzinfo=UTC)
_LATER_END = datetime(2026, 10, 26, 0, 0, tzinfo=UTC)


def _evidence() -> EvidenceReference:
    return EvidenceReference(
        evidence_id=uuid4(),
        evidence_type="provider-observation",
        source_reference="fixture://metrics/week",
        observed_at=_WHEN,
        safe_summary="Injected weekly metrics citation",
    )


def _row(
    *,
    listing_id: UUID,
    listing_version: int,
    window_start: datetime,
    window_end: datetime,
    evidence: EvidenceReference,
    views: int,
    orders: int,
    reconciled: bool,
) -> dict[str, object]:
    return {
        "snapshot_id": uuid4(),
        "listing_id": listing_id,
        "listing_version": listing_version,
        "provider": "etsy",
        "observed_at": _WHEN,
        "views": views,
        "favourites": 2,
        "orders": orders,
        "gross_revenue": Decimal("12.50"),
        "currency": "GBP",
        "reconciled": reconciled,
        "window_start": window_start,
        "window_end": window_end,
        "evidence": evidence,
    }


def _effect(
    operation: str,
    state: Literal["CONFIRMED", "ABSENT", "UNKNOWN"],
) -> EffectReference:
    return EffectReference(
        idempotency_key=f"{operation}:{state}:{uuid4()}",
        provider="etsy",
        operation=operation,
        provider_object_id=None if state == "ABSENT" else "listing-1",
        effect_state=state,
        observed_at=_WHEN,
    )


def test_fixture_maps_one_snapshot_per_listing_version_and_window() -> None:
    listing_id = uuid4()
    other_listing = uuid4()
    first_evidence = _evidence()
    second_evidence = _evidence()
    first = _row(
        listing_id=listing_id,
        listing_version=1,
        window_start=_WEEK,
        window_end=_WEEK_END,
        evidence=first_evidence,
        views=4,
        orders=1,
        reconciled=True,
    )
    second = _row(
        listing_id=listing_id,
        listing_version=1,
        window_start=_NEXT,
        window_end=_NEXT_END,
        evidence=second_evidence,
        views=6,
        orders=2,
        reconciled=False,
    )
    other = _row(
        listing_id=other_listing,
        listing_version=1,
        window_start=_WEEK,
        window_end=_WEEK_END,
        evidence=_evidence(),
        views=1,
        orders=0,
        reconciled=True,
    )
    next_version = _row(
        listing_id=listing_id,
        listing_version=2,
        window_start=_WEEK,
        window_end=_WEEK_END,
        evidence=_evidence(),
        views=3,
        orders=1,
        reconciled=True,
    )

    loaded = snapshots_from_fixture((first, second))

    assert len(loaded) == 2
    assert all(isinstance(item, FixtureObservation) for item in loaded)
    assert all(isinstance(item.snapshot, MetricsSnapshot) for item in loaded)
    assert all(not hasattr(item, "views") for item in loaded)
    assert all(not hasattr(item, "orders") for item in loaded)
    assert all(not hasattr(item, "cumulative_views") for item in loaded)
    week = loaded[0].snapshot
    assert week.listing_version == 1
    assert week.provider == "etsy"
    assert week.observed_at == _WHEN
    assert week.views == 4
    assert week.favourites == 2
    assert week.orders == 1
    assert week.gross_revenue == Decimal("12.50")
    assert week.currency == "GBP"
    assert week.reconciled is True
    assert week.source_evidence == (first_evidence,)
    assert len(week.source_evidence) == 1
    assert loaded[1].snapshot.source_evidence == (second_evidence,)
    assert loaded[1].snapshot.reconciled is False
    totals = cumulative_totals(tuple(item.snapshot for item in loaded))
    assert isinstance(totals, CumulativeTotals)
    assert totals.views == 10
    assert totals.orders == 3
    assert not hasattr(totals, "snapshot_id")
    assert len(snapshots_from_fixture((first, other, next_version))) == 3

    duplicate = dict(first)
    duplicate["snapshot_id"] = uuid4()
    duplicate["views"] = 99
    with pytest.raises(MetricsFixtureRefusal):
        snapshots_from_fixture((first, duplicate))

    extra = dict(second)
    extra["snapshot_id"] = uuid4()
    extra["window_start"] = _LATER
    extra["window_end"] = _LATER_END
    extra["conversion_rate"] = Decimal("0.20")
    with pytest.raises(MetricsFixtureRefusal):
        snapshots_from_fixture((extra,))

    writable_bag = dict(second)
    writable_bag["snapshot_id"] = uuid4()
    writable_bag["window_start"] = _LATER
    writable_bag["window_end"] = _LATER_END
    writable_bag["cumulative_views"] = 100
    writable_bag["cumulative_orders"] = 9
    with pytest.raises(MetricsFixtureRefusal):
        snapshots_from_fixture((writable_bag,))

    two_citations = dict(second)
    two_citations["snapshot_id"] = uuid4()
    two_citations["window_start"] = _LATER
    two_citations["window_end"] = _LATER_END
    two_citations["evidence"] = (second_evidence, _evidence())
    with pytest.raises(MetricsFixtureRefusal):
        snapshots_from_fixture((two_citations,))


def test_plan_weekly_collects_each_active_listing_once_per_window() -> None:
    module_source = inspect.getsource(metrics_fixture)
    assert "httpx" not in module_source
    assert "os.environ" not in module_source
    assert "scheduler" not in module_source
    assert "PENDING" not in module_source
    assert "READY" not in module_source
    imported = _imported_roots(module_source)
    assert "httpx" not in imported
    assert "socket" not in imported
    assert "scheduler" not in imported
    assert inspect.isfunction(plan_weekly)

    active = ActiveListing(listing_id=uuid4(), listing_version=1, active=True)
    paused = ActiveListing(listing_id=uuid4(), listing_version=3, active=False)
    second = ActiveListing(listing_id=uuid4(), listing_version=2, active=True)
    prior = _snapshot(active.listing_id, views=4, orders=1)
    before = prior.model_dump()

    plan = plan_weekly(
        (active, paused, second),
        window_start=_WEEK,
        window_end=_WEEK_END,
        prior_snapshots=(prior,),
    )

    assert isinstance(plan, WeeklyPlan)
    assert plan.prior_snapshots == (prior,)
    assert plan.prior_snapshots[0] is prior
    assert prior.model_dump() == before
    assert [record.kind for record in plan.records] == ["collection", "collection", "shop_review"]
    assert [record.listing_id for record in plan.records] == [
        active.listing_id,
        second.listing_id,
        None,
    ]
    assert plan.records[0].listing_version == 1
    assert plan.records[1].listing_version == 2
    assert plan.records[2].listing_version is None
    assert all(isinstance(record, CollectionRecord) for record in plan.records)
    assert all(
        record.window_start == _WEEK and record.window_end == _WEEK_END for record in plan.records
    )
    assert not any(hasattr(record, "views") for record in plan.records)

    again = plan_weekly(
        (active, paused, second),
        window_start=_WEEK,
        window_end=_WEEK_END,
        prior_snapshots=(prior,),
        existing_records=plan.records,
    )
    assert again.records == ()
    assert all(record.kind != "collection" for record in again.records)
    assert again.prior_snapshots[0] is prior
    assert prior.model_dump() == before

    later = plan_weekly(
        (active,),
        window_start=_NEXT,
        window_end=_NEXT_END,
        prior_snapshots=(prior,),
        existing_records=plan.records,
    )
    assert [record.kind for record in later.records] == ["collection", "shop_review"]
    assert later.prior_snapshots[0] is prior


def test_plan_monthly_follows_monthly_cadence_not_a_fourth_week() -> None:
    shop_id = uuid4()
    fourth_only = plan_monthly(
        cadence="monthly",
        weekly_fire_count=4,
        month_due=False,
        window_start=_WEEK,
        window_end=_WEEK_END,
        shop_id=shop_id,
    )
    assert fourth_only is None

    record = plan_monthly(
        cadence="monthly",
        weekly_fire_count=1,
        month_due=True,
        window_start=_WEEK,
        window_end=_WEEK_END,
        shop_id=shop_id,
    )
    assert isinstance(record, MonthlyRecord)
    assert record.cadence == "monthly"
    assert len(record.jobs) == 3
    assert all(isinstance(job, PlannedJob) for job in record.jobs)
    assert all(not isinstance(job, str) for job in record.jobs)
    assert [job.role for job in record.jobs] == ["research", "build-slot", "scale"]
    assert [job.job_type for job in record.jobs] == [
        "ResearchCollectionJob",
        "BuildSlotJob",
        "ScaleEvaluationJob",
    ]
    assert all(job.shop_id == shop_id for job in record.jobs)
    assert all(job.window_start == _WEEK and job.window_end == _WEEK_END for job in record.jobs)
    assert all(job.admitted_event is EventName.MONTHLY_REVIEW_COMPLETED for job in record.jobs)
    assert not any(hasattr(job, "status") for job in record.jobs)

    with pytest.raises(MetricsFixtureRefusal):
        plan_monthly(
            cadence="fourth-week",
            weekly_fire_count=4,
            month_due=True,
            window_start=_WEEK,
            window_end=_WEEK_END,
            shop_id=shop_id,
        )


def test_milestones_follow_confirmed_effects_and_measured_minutes() -> None:
    cull = _effect("CULL", "CONFIRMED")
    unconfirmed = _effect("CULL", "UNKNOWN")
    publish = _effect("ETSY_PUBLISH", "CONFIRMED")
    spec_id = uuid4()

    present = derive_milestones(
        MilestoneInput(
            effects=(publish, unconfirmed, cull),
            successor_spec_id=spec_id,
            measured=False,
            operator_minutes=None,
        )
    )
    assert isinstance(present, MilestoneReport)
    assert present.first_cull is cull
    assert present.first_multiplied_winner == spec_id
    assert present.operator_minutes is None

    absent = derive_milestones(
        MilestoneInput(
            effects=(publish, unconfirmed),
            successor_spec_id=None,
            measured=False,
            operator_minutes=None,
        )
    )
    assert absent.first_cull is None
    assert absent.first_multiplied_winner is None
    assert absent.operator_minutes is None

    measured_zero = derive_milestones(
        MilestoneInput(
            effects=(),
            successor_spec_id=None,
            measured=True,
            operator_minutes=0,
        )
    )
    assert measured_zero.first_cull is None
    assert measured_zero.first_multiplied_winner is None
    assert measured_zero.operator_minutes == 0

    with pytest.raises(MetricsFixtureRefusal):
        derive_milestones(
            MilestoneInput(
                effects=(cull,),
                successor_spec_id=spec_id,
                measured=False,
                operator_minutes=0,
            )
        )


def _snapshot(listing_id: UUID, *, views: int, orders: int) -> MetricsSnapshot:
    return MetricsSnapshot(
        snapshot_id=uuid4(),
        listing_id=listing_id,
        listing_version=1,
        provider="etsy",
        observed_at=_WHEN,
        views=views,
        favourites=2,
        orders=orders,
        gross_revenue=Decimal("12.50"),
        currency="GBP",
        reconciled=True,
        source_evidence=(_evidence(),),
    )


def _imported_roots(source: str) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            found.add(node.module)
    return found
