"""Persist loop triggers and confirm a cull from a fixture read.

Rows live in a ledger keyed like ``scheduled_triggers.trigger_key``. A second
write of the same key adds nothing and does not move ``next_fire_at``.
``LISTING_CULLED`` is returned only after a fixture status of ``CONFIRMED``.
This module does not call the scheduler and does not write to a provider.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from money_machine.assets.metrics_fixture import MonthlyRecord, WeeklyPlan
from money_machine.assets.portfolio_eligibility import PortfolioResult
from money_machine.domain.enums import DecisionType
from money_machine.domain.events import EventName

type TriggerKind = Literal["WEEKLY_REVIEW", "MONTHLY_DEEP_PASS", "BUILD_SLOT"]
type FixtureStatus = Literal["CONFIRMED", "UNKNOWN", "FAILED"]

_WEEKLY_CRON = "0 9 * * 1"
_MONTHLY_CRON = "0 9 1 * *"


class ClosedLoopRefusal(ValueError):
    """The ledger cannot store the row or confirm the cull."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class StoredTrigger:
    """One durable trigger row. The key is the idempotency identity."""

    shop_id: UUID
    trigger_kind: TriggerKind
    trigger_key: str
    cron_expression: str
    next_fire_at: datetime
    active: bool


@dataclass(frozen=True, slots=True)
class LessonRow:
    """The experiment note kept with the listing. Nothing here is deleted."""

    listing_id: UUID
    deactivation_job_id: UUID
    lesson: str
    retained: bool


@dataclass(frozen=True, slots=True)
class CullConfirmation:
    """Fixture read result. An unconfirmed read carries no cull event."""

    event_names: tuple[EventName, ...]
    lesson: LessonRow | None
    retained_artifact_ids: tuple[UUID, ...]
    deactivation_executed: bool


class TriggerLedger:
    """In-process unique index for trigger keys."""

    def __init__(self) -> None:
        self._rows: dict[str, StoredTrigger] = {}

    def rows(self) -> tuple[StoredTrigger, ...]:
        return tuple(self._rows.values())

    def insert(self, row: StoredTrigger) -> StoredTrigger | None:
        """Store ``row`` when its key is new. An existing key is left as it was."""
        if row.trigger_key in self._rows:
            return None
        self._rows[row.trigger_key] = row
        return row


def persist_weekly_plan(
    ledger: TriggerLedger,
    *,
    shop_id: UUID,
    plan: WeeklyPlan,
    next_fire_at: datetime,
) -> tuple[StoredTrigger, ...]:
    """Insert one weekly trigger per new plan record. Existing keys stay put."""
    inserted: list[StoredTrigger] = []
    for record in plan.records:
        if record.kind == "collection":
            if record.listing_id is None:
                raise ClosedLoopRefusal("collection_listing")
            trigger_key = (
                f"weekly:{shop_id}:collection:{record.listing_id}:{record.window_start.isoformat()}"
            )
        elif record.kind == "shop_review":
            trigger_key = f"weekly:{shop_id}:shop-review:{record.window_start.isoformat()}"
        else:
            raise ClosedLoopRefusal("record_kind")
        stored = ledger.insert(
            StoredTrigger(
                shop_id=shop_id,
                trigger_kind="WEEKLY_REVIEW",
                trigger_key=trigger_key,
                cron_expression=_WEEKLY_CRON,
                next_fire_at=next_fire_at,
                active=True,
            )
        )
        if stored is not None:
            inserted.append(stored)
    return tuple(inserted)


def persist_monthly_record(
    ledger: TriggerLedger,
    record: MonthlyRecord | None,
) -> StoredTrigger | None:
    """Insert one monthly deep-pass trigger. A missing record inserts nothing."""
    if record is None:
        return None
    if not record.jobs:
        raise ClosedLoopRefusal("monthly_jobs")
    shop_id = record.jobs[0].shop_id
    if any(job.shop_id != shop_id for job in record.jobs):
        raise ClosedLoopRefusal("monthly_shop")
    return ledger.insert(
        StoredTrigger(
            shop_id=shop_id,
            trigger_kind="MONTHLY_DEEP_PASS",
            trigger_key=f"monthly:{shop_id}:{record.window_start.isoformat()}",
            cron_expression=_MONTHLY_CRON,
            next_fire_at=record.window_end,
            active=True,
        )
    )


def confirm_fixture_cull(
    result: PortfolioResult,
    *,
    fixture_status: FixtureStatus,
    lesson: str,
    artifact_ids: tuple[UUID, ...],
) -> CullConfirmation:
    """Return ``LISTING_CULLED`` only when the fixture read is ``CONFIRMED``.

    The deactivation is still unexecuted. Artifacts named by the caller are
    copied onto the confirmation and are not removed.
    """
    if EventName.LISTING_CULLED in result.event_names:
        raise ClosedLoopRefusal("listing_culled")
    if result.decision is not DecisionType.CULL:
        return CullConfirmation(
            event_names=(),
            lesson=None,
            retained_artifact_ids=(),
            deactivation_executed=False,
        )
    if result.deactivation_job_id is None:
        raise ClosedLoopRefusal("deactivation_job")
    if fixture_status != "CONFIRMED":
        return CullConfirmation(
            event_names=(),
            lesson=None,
            retained_artifact_ids=(),
            deactivation_executed=False,
        )
    text = lesson.strip()
    if text == "":
        raise ClosedLoopRefusal("lesson")
    return CullConfirmation(
        event_names=(EventName.LISTING_CULLED,),
        lesson=LessonRow(
            listing_id=result.listing_id,
            deactivation_job_id=result.deactivation_job_id,
            lesson=text,
            retained=True,
        ),
        retained_artifact_ids=artifact_ids,
        deactivation_executed=False,
    )
