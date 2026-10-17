"""Exception views derived from the in-memory console read model.

Each named view has a ready state, an empty state, and an error state.
A routine decision is not an approval request. A blocked job is not a blocker.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from money_machine.assets.operator_console import (
    BlockerView,
    CompletionView,
    ConsoleReadModel,
    ConsoleRefusal,
    DecisionKind,
    JobView,
    ListingView,
    Page,
)

type ViewStatus = Literal["ready", "empty", "error"]
_PAGE_LIMIT = 50


@dataclass(frozen=True, slots=True)
class NowView:
    """What is running, what finished, what is next, and whether action is required."""

    status: ViewStatus
    running: tuple[JobView, ...]
    recent_completions: tuple[CompletionView, ...]
    next_scheduled: tuple[JobView, ...]
    action_required: bool
    error: str | None


@dataclass(frozen=True, slots=True)
class PipelineRow:
    """One stage joined to the workflow that owns it."""

    stage: str
    experiment_count: int
    owning_agent: str
    elapsed_seconds: int
    next_transition: str
    blocked_dependency: str | None


@dataclass(frozen=True, slots=True)
class PipelineView:
    """Product experiments by stage."""

    status: ViewStatus
    rows: tuple[PipelineRow, ...]
    error: str | None


@dataclass(frozen=True, slots=True)
class ShopBoard:
    """Listings split by state. Counts stay on each listing."""

    status: ViewStatus
    active: tuple[ListingView, ...]
    draft: tuple[ListingView, ...]
    deactivated: tuple[ListingView, ...]
    error: str | None


@dataclass(frozen=True, slots=True)
class BlockedView:
    """Only the five real blocker kinds."""

    status: ViewStatus
    blockers: tuple[BlockerView, ...]
    error: str | None


@dataclass(frozen=True, slots=True)
class DecisionRow:
    """A shown decision. ``approval_request`` stays false for a routine decision."""

    decision_id: str
    kind: DecisionKind
    evidence: str
    status: str
    approval_request: bool


@dataclass(frozen=True, slots=True)
class DecisionsView:
    """Hold, repair, cull, multiply, and successor created."""

    status: ViewStatus
    rows: tuple[DecisionRow, ...]
    error: str | None


@dataclass(frozen=True, slots=True)
class IncidentRow:
    """One buyer issue and its repair evidence."""

    incident_id: str
    buyer_issue: str
    severity: str
    repair_step: str
    response_status: str
    resolution_evidence: str


@dataclass(frozen=True, slots=True)
class IncidentsView:
    """Incidents derived from the read model."""

    status: ViewStatus
    rows: tuple[IncidentRow, ...]
    error: str | None


@dataclass(frozen=True, slots=True)
class SettingsView:
    """A read of autonomy and provider status. Caps are not written."""

    status: ViewStatus
    mode: str
    publication_cap: int
    purchase_cap: int
    loop_day: int
    posthog: str
    provider: str
    error: str | None


@dataclass(frozen=True, slots=True)
class ConsoleViews:
    """The seven named views. A missing view is not this value."""

    now: NowView
    pipeline: PipelineView
    shop: ShopBoard
    blocked: BlockedView
    decisions: DecisionsView
    incidents: IncidentsView
    settings: SettingsView


def render_console(model: ConsoleReadModel, *, cursor: str | None = None) -> ConsoleViews:
    """Derive every named view from ``model``. A bad cursor is an error state."""
    return ConsoleViews(
        now=_now(model, cursor),
        pipeline=_pipeline(model, cursor),
        shop=_shop(model, cursor),
        blocked=_blocked(model, cursor),
        decisions=_decisions(model, cursor),
        incidents=_incidents(model, cursor),
        settings=_settings(model, cursor),
    )


def _collect[Item](
    read: Callable[..., Page[Item]],
    *,
    cursor: str | None,
    **kwargs: str,
) -> tuple[Item, ...]:
    collected: list[Item] = []
    current = cursor
    while True:
        page = read(cursor=current, limit=_PAGE_LIMIT, **kwargs)
        collected.extend(page.items)
        if page.next_cursor is None:
            return tuple(collected)
        current = page.next_cursor


def _now(model: ConsoleReadModel, cursor: str | None) -> NowView:
    try:
        running = _collect(model.job_page, cursor=cursor, status="running")
        scheduled = _collect(model.job_page, cursor=None, status="ready")
        completions = _collect(model.completion_page, cursor=None)
        health = model.system_health()
    except ConsoleRefusal as error:
        return NowView(
            status="error",
            running=(),
            recent_completions=(),
            next_scheduled=(),
            action_required=False,
            error=error.code,
        )
    status: ViewStatus = (
        "empty"
        if not running and not scheduled and not completions and not health.action_required
        else "ready"
    )
    return NowView(
        status=status,
        running=running,
        recent_completions=completions,
        next_scheduled=scheduled,
        action_required=health.action_required,
        error=None,
    )


def _pipeline(model: ConsoleReadModel, cursor: str | None) -> PipelineView:
    try:
        stages = _collect(model.pipeline_stages, cursor=cursor)
        workflows = _collect(model.workflow_page, cursor=None)
    except ConsoleRefusal as error:
        return PipelineView(status="error", rows=(), error=error.code)
    rows: list[PipelineRow] = []
    for stage in stages:
        owners = tuple(item for item in workflows if item.stage == stage.stage)
        owner = max(owners, key=lambda item: (item.elapsed_seconds, item.workflow_id), default=None)
        rows.append(
            PipelineRow(
                stage=stage.stage,
                experiment_count=stage.experiment_count,
                owning_agent="" if owner is None else owner.owning_agent,
                elapsed_seconds=0 if owner is None else owner.elapsed_seconds,
                next_transition="" if owner is None else owner.next_transition,
                blocked_dependency=None if owner is None else owner.blocked_dependency,
            )
        )
    status: ViewStatus = "empty" if not rows else "ready"
    return PipelineView(status=status, rows=tuple(rows), error=None)


def _shop(model: ConsoleReadModel, cursor: str | None) -> ShopBoard:
    try:
        listings = _collect(model.listing_page, cursor=cursor)
    except ConsoleRefusal as error:
        return ShopBoard(status="error", active=(), draft=(), deactivated=(), error=error.code)
    active = tuple(item for item in listings if item.state == "active")
    draft = tuple(item for item in listings if item.state == "draft")
    deactivated = tuple(item for item in listings if item.state == "deactivated")
    status: ViewStatus = "empty" if not listings else "ready"
    return ShopBoard(
        status=status,
        active=active,
        draft=draft,
        deactivated=deactivated,
        error=None,
    )


def _blocked(model: ConsoleReadModel, cursor: str | None) -> BlockedView:
    try:
        blockers = _collect(model.blocker_page, cursor=cursor)
    except ConsoleRefusal as error:
        return BlockedView(status="error", blockers=(), error=error.code)
    status: ViewStatus = "empty" if not blockers else "ready"
    return BlockedView(status=status, blockers=blockers, error=None)


def _decisions(model: ConsoleReadModel, cursor: str | None) -> DecisionsView:
    try:
        decisions = _collect(model.decision_page, cursor=cursor)
    except ConsoleRefusal as error:
        return DecisionsView(status="error", rows=(), error=error.code)
    rows = tuple(
        DecisionRow(
            decision_id=item.decision_id,
            kind=item.kind,
            evidence=item.evidence,
            status=item.status,
            approval_request=not item.routine,
        )
        for item in decisions
    )
    status: ViewStatus = "empty" if not rows else "ready"
    return DecisionsView(status=status, rows=rows, error=None)


def _incidents(model: ConsoleReadModel, cursor: str | None) -> IncidentsView:
    try:
        incidents = _collect(model.incident_page, cursor=cursor)
    except ConsoleRefusal as error:
        return IncidentsView(status="error", rows=(), error=error.code)
    rows = tuple(
        IncidentRow(
            incident_id=item.incident_id,
            buyer_issue=item.summary,
            severity=item.severity,
            repair_step=item.repair_step,
            response_status=item.response_status,
            resolution_evidence=item.resolution_evidence,
        )
        for item in incidents
    )
    status: ViewStatus = "empty" if not rows else "ready"
    return IncidentsView(status=status, rows=rows, error=None)


def _settings(model: ConsoleReadModel, cursor: str | None) -> SettingsView:
    try:
        settings = model.autonomy_settings()
        integrations = _collect(model.integration_page, cursor=cursor)
        shop = model.current_shop()
    except ConsoleRefusal as error:
        return SettingsView(
            status="error",
            mode="",
            publication_cap=0,
            purchase_cap=0,
            loop_day=0,
            posthog="",
            provider="",
            error=error.code,
        )
    status: ViewStatus = "empty" if shop is None and not integrations else "ready"
    return SettingsView(
        status=status,
        mode=settings.mode,
        publication_cap=settings.publication_cap,
        purchase_cap=settings.purchase_cap,
        loop_day=settings.loop_day,
        posthog=settings.posthog,
        provider=settings.provider,
        error=None,
    )
