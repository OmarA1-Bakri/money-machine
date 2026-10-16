"""Level 1 pins for persisted loop triggers and a fixture-confirmed cull."""

from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

import pytest

from money_machine.assets.closed_loop_store import (
    ClosedLoopRefusal,
    TriggerLedger,
    confirm_fixture_cull,
    persist_monthly_record,
    persist_weekly_plan,
)
from money_machine.assets.metrics_fixture import (
    ActiveListing,
    MonthlyRecord,
    PlannedJob,
    plan_weekly,
)
from money_machine.assets.portfolio_eligibility import PortfolioResult
from money_machine.domain.enums import DecisionType
from money_machine.domain.events import EventName

_START = datetime(2026, 10, 5, tzinfo=UTC)
_END = datetime(2026, 10, 12, tzinfo=UTC)
_FIRE = datetime(2026, 10, 12, 9, tzinfo=UTC)


def _uuid(number: int) -> UUID:
    return UUID(int=number)


def _weekly_plan():
    listings = (
        ActiveListing(listing_id=_uuid(1), listing_version=1, active=True),
        ActiveListing(listing_id=_uuid(2), listing_version=1, active=False),
        ActiveListing(listing_id=_uuid(3), listing_version=2, active=True),
    )
    return plan_weekly(listings, window_start=_START, window_end=_END, prior_snapshots=())


def _cull(*, job_id: UUID | None) -> PortfolioResult:
    return PortfolioResult(
        listing_id=_uuid(1),
        decision_id=_uuid(9),
        decision=DecisionType.CULL,
        decided_at=_FIRE,
        snapshot_id=_uuid(8),
        event_names=(EventName.LISTING_CULL_REQUESTED,),
        deactivation_job_id=job_id,
        deactivation_executed=False,
    )


def test_weekly_plan_persists_one_trigger_per_new_record() -> None:
    ledger = TriggerLedger()
    inserted = persist_weekly_plan(
        ledger, shop_id=_uuid(7), plan=_weekly_plan(), next_fire_at=_FIRE
    )

    assert [row.trigger_kind for row in inserted] == [
        "WEEKLY_REVIEW",
        "WEEKLY_REVIEW",
        "WEEKLY_REVIEW",
    ]
    assert [row.trigger_key for row in inserted] == [
        f"weekly:{_uuid(7)}:collection:{_uuid(1)}:{_START.isoformat()}",
        f"weekly:{_uuid(7)}:collection:{_uuid(3)}:{_START.isoformat()}",
        f"weekly:{_uuid(7)}:shop-review:{_START.isoformat()}",
    ]
    assert all(
        row.cron_expression == "0 9 * * 1" and row.active and row.next_fire_at == _FIRE
        for row in inserted
    )
    assert ledger.rows() == inserted


def test_second_weekly_persist_adds_nothing_and_keeps_the_first_fire_time() -> None:
    ledger = TriggerLedger()
    first = persist_weekly_plan(ledger, shop_id=_uuid(7), plan=_weekly_plan(), next_fire_at=_FIRE)
    later = _FIRE.replace(day=19)
    second = persist_weekly_plan(ledger, shop_id=_uuid(7), plan=_weekly_plan(), next_fire_at=later)

    assert second == ()
    assert ledger.rows() == first
    assert all(row.next_fire_at == _FIRE for row in ledger.rows())


def test_monthly_record_persists_a_deep_pass_and_a_weekly_plan_does_not() -> None:
    ledger = TriggerLedger()
    persist_weekly_plan(ledger, shop_id=_uuid(7), plan=_weekly_plan(), next_fire_at=_FIRE)
    record = MonthlyRecord(
        cadence="monthly",
        window_start=_START,
        window_end=_END,
        jobs=(
            PlannedJob(
                job_type="ResearchCollectionJob",
                role="research",
                shop_id=_uuid(7),
                window_start=_START,
                window_end=_END,
                admitted_event=EventName.RESEARCH_COMPLETED,
            ),
        ),
    )

    inserted = persist_monthly_record(ledger, record)

    assert inserted is not None
    assert inserted.trigger_kind == "MONTHLY_DEEP_PASS"
    assert inserted.trigger_key == f"monthly:{_uuid(7)}:{_START.isoformat()}"
    assert inserted.cron_expression == "0 9 1 * *"
    assert [row.trigger_kind for row in ledger.rows()].count("MONTHLY_DEEP_PASS") == 1
    assert persist_monthly_record(ledger, record) is None
    assert persist_monthly_record(ledger, None) is None


def test_confirmed_fixture_emits_listing_culled_and_retains_the_lesson() -> None:
    artifacts = (_uuid(4), _uuid(5))
    confirmed = confirm_fixture_cull(
        _cull(job_id=_uuid(6)),
        fixture_status="CONFIRMED",
        lesson="bottom of the cohort after thirty live periods",
        artifact_ids=artifacts,
    )

    assert confirmed.event_names == (EventName.LISTING_CULLED,)
    assert confirmed.lesson is not None
    assert confirmed.lesson.listing_id == _uuid(1)
    assert confirmed.lesson.deactivation_job_id == _uuid(6)
    assert confirmed.lesson.retained is True
    assert confirmed.retained_artifact_ids == artifacts
    assert confirmed.deactivation_executed is False


def test_unknown_fixture_emits_nothing_and_keeps_no_lesson() -> None:
    statuses: tuple[Literal["UNKNOWN", "FAILED"], ...] = ("UNKNOWN", "FAILED")
    for status in statuses:
        confirmation = confirm_fixture_cull(
            _cull(job_id=_uuid(6)),
            fixture_status=status,
            lesson="bottom of the cohort after thirty live periods",
            artifact_ids=(_uuid(4),),
        )
        assert confirmation.event_names == ()
        assert confirmation.lesson is None
        assert confirmation.retained_artifact_ids == ()


def test_hold_and_a_blank_lesson_do_not_become_a_cull() -> None:
    hold = replace(
        _cull(job_id=_uuid(6)),
        decision=DecisionType.HOLD,
        deactivation_job_id=None,
        event_names=(EventName.LISTING_HELD,),
    )
    confirmation = confirm_fixture_cull(
        hold,
        fixture_status="CONFIRMED",
        lesson="bottom of the cohort after thirty live periods",
        artifact_ids=(_uuid(4),),
    )
    assert confirmation.event_names == ()
    assert confirmation.lesson is None

    with pytest.raises(ClosedLoopRefusal, match="lesson"):
        confirm_fixture_cull(
            _cull(job_id=_uuid(6)),
            fixture_status="CONFIRMED",
            lesson="  ",
            artifact_ids=(_uuid(4),),
        )


def test_listing_culled_named_before_confirmation_is_refused() -> None:
    early = replace(_cull(job_id=_uuid(6)), event_names=(EventName.LISTING_CULLED,))
    with pytest.raises(ClosedLoopRefusal, match="listing_culled"):
        confirm_fixture_cull(
            early,
            fixture_status="CONFIRMED",
            lesson="bottom of the cohort after thirty live periods",
            artifact_ids=(_uuid(4),),
        )


def test_cull_without_a_job_id_is_refused() -> None:
    with pytest.raises(ClosedLoopRefusal, match="deactivation_job"):
        confirm_fixture_cull(
            _cull(job_id=None),
            fixture_status="CONFIRMED",
            lesson="bottom of the cohort after thirty live periods",
            artifact_ids=(),
        )


def test_store_does_not_call_the_scheduler() -> None:
    import ast

    import money_machine.assets.closed_loop_store as store

    source = inspect.getsource(store)
    modules: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append(node.module)
    assert all("scheduler" not in module for module in modules)
    assert "schedule_maturity_timer" not in source
    assert "socket" not in source
    assert "httpx" not in source
    assert "requests" not in source
