"""In-memory operator console read model. No socket and no provider call.

Every surface returns a typed value. An empty store returns an empty page.
Pagination is a stable id cursor. This module has no writer for caps,
autonomy, or telemetry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

type JobStatus = Literal["ready", "running", "blocked"]
type ListingState = Literal["active", "draft", "deactivated"]
type DecisionKind = Literal["hold", "repair", "cull", "multiply", "successor_created"]
type IntegrationState = Literal["offline", "held"]

_JOB_STATUSES = frozenset({"ready", "running", "blocked"})
_LISTING_STATES = frozenset({"active", "draft", "deactivated"})
_DECISION_KINDS = frozenset({"hold", "repair", "cull", "multiply", "successor_created"})
_INTEGRATION_STATES = frozenset({"offline", "held"})
_MAX_LIMIT = 50


class ConsoleRefusal(ValueError):
    """The read model cannot return this page."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class Page[Item]:
    """One stable page. ``next_cursor`` is none on the last page."""

    items: tuple[Item, ...]
    next_cursor: str | None


@dataclass(frozen=True, slots=True)
class ShopView:
    """The current shop. Absent when the store is empty."""

    shop_id: str
    name: str
    currency: str


@dataclass(frozen=True, slots=True)
class WorkflowView:
    """One workflow row."""

    workflow_id: str
    name: str
    stage: str
    owning_agent: str
    elapsed_seconds: int
    next_transition: str
    blocked_dependency: str | None


@dataclass(frozen=True, slots=True)
class PipelineStageView:
    """Experiments sitting in one stage."""

    stage: str
    experiment_count: int


@dataclass(frozen=True, slots=True)
class JobView:
    """A ready, running, or blocked job."""

    job_id: str
    workflow_id: str
    job_type: str
    status: JobStatus
    attempt: int


@dataclass(frozen=True, slots=True)
class ProductView:
    """A product row. Variants are a separate page."""

    product_id: str
    name: str


@dataclass(frozen=True, slots=True)
class VariantView:
    """A variant of one product."""

    variant_id: str
    product_id: str
    name: str


@dataclass(frozen=True, slots=True)
class ListingView:
    """Listing state for one product."""

    listing_id: str
    product_id: str
    state: ListingState
    age_days: int
    views: int
    favourites: int
    sales: int
    decision: str
    next_review_at: str


@dataclass(frozen=True, slots=True)
class WeeklyMetricView:
    """One shop week. Commerce figures stay caller-supplied."""

    week_start: str
    views: int
    favourites: int
    sales: int


@dataclass(frozen=True, slots=True)
class DecisionView:
    """A recorded decision. A routine decision is not an approval request."""

    decision_id: str
    kind: DecisionKind
    evidence: str
    status: str
    routine: bool


@dataclass(frozen=True, slots=True)
class IncidentView:
    """One incident row."""

    incident_id: str
    summary: str
    severity: str
    repair_step: str
    response_status: str


@dataclass(frozen=True, slots=True)
class IntegrationView:
    """Provider status. A live connection is not a value this model stores."""

    name: str
    status: IntegrationState


@dataclass(frozen=True, slots=True)
class MilestoneView:
    """Progress against one named milestone."""

    name: str
    completed: int
    total: int


@dataclass(frozen=True, slots=True)
class AutonomySettings:
    """A read of the caps. This model does not write them."""

    mode: str
    publication_cap: int
    purchase_cap: int
    loop_day: int
    posthog: Literal["offline"]
    provider: Literal["unread"]


@dataclass(frozen=True, slots=True)
class SystemHealth:
    """Counts derived from the jobs already on the model."""

    running: int
    blocked: int
    action_required: bool


def _opaque(value: object) -> object:
    """Hide a typed value so a runtime check stays meaningful."""
    return value


def _text(value: str, code: str) -> str:
    raw = _opaque(value)
    if not isinstance(raw, str) or raw.strip() == "":
        raise ConsoleRefusal(code)
    return raw


def _count(value: int, code: str) -> int:
    raw = _opaque(value)
    if not isinstance(raw, int) or isinstance(raw, bool) or raw < 0:
        raise ConsoleRefusal(code)
    return raw


def _unique(ids: tuple[str, ...], code: str) -> None:
    if len(ids) != len(set(ids)):
        raise ConsoleRefusal(code)


def _page[Item](
    items: tuple[Item, ...],
    *,
    cursor: str | None,
    limit: int,
    identity: Callable[[Item], str],
) -> Page[Item]:
    raw_limit = _opaque(limit)
    if (
        not isinstance(raw_limit, int)
        or isinstance(raw_limit, bool)
        or raw_limit < 1
        or raw_limit > _MAX_LIMIT
    ):
        raise ConsoleRefusal("limit")
    limit = raw_limit
    ordered = tuple(sorted(items, key=identity))
    start = 0
    if cursor is not None:
        if not isinstance(_opaque(cursor), str):
            raise ConsoleRefusal("cursor")
        positions = [identity(item) for item in ordered]
        if cursor not in positions:
            raise ConsoleRefusal("cursor")
        start = positions.index(cursor) + 1
    window = ordered[start : start + limit]
    next_cursor = identity(window[-1]) if start + limit < len(ordered) else None
    return Page(items=window, next_cursor=next_cursor)


@dataclass(frozen=True, slots=True)
class ConsoleReadModel:
    """Typed surfaces for the operator console. Construction validates; reads do not."""

    shop: ShopView | None = None
    workflows: tuple[WorkflowView, ...] = ()
    stages: tuple[PipelineStageView, ...] = ()
    jobs: tuple[JobView, ...] = ()
    products: tuple[ProductView, ...] = ()
    variants: tuple[VariantView, ...] = ()
    listings: tuple[ListingView, ...] = ()
    weekly_metrics: tuple[WeeklyMetricView, ...] = ()
    decisions: tuple[DecisionView, ...] = ()
    incidents: tuple[IncidentView, ...] = ()
    integrations: tuple[IntegrationView, ...] = ()
    milestones: tuple[MilestoneView, ...] = ()
    autonomy: AutonomySettings = AutonomySettings(
        mode="held",
        publication_cap=0,
        purchase_cap=0,
        loop_day=0,
        posthog="offline",
        provider="unread",
    )

    def __post_init__(self) -> None:
        self._validate()

    def current_shop(self) -> ShopView | None:
        """Return the shop, or none when the store has no shop."""
        return self.shop

    def workflow_page(self, *, cursor: str | None = None, limit: int = 20) -> Page[WorkflowView]:
        """Return workflows in id order."""
        return _page(
            self.workflows, cursor=cursor, limit=limit, identity=lambda item: item.workflow_id
        )

    def pipeline_stages(
        self, *, cursor: str | None = None, limit: int = 20
    ) -> Page[PipelineStageView]:
        """Return pipeline stages in name order."""
        return _page(self.stages, cursor=cursor, limit=limit, identity=lambda item: item.stage)

    def job_page(self, *, status: str, cursor: str | None = None, limit: int = 20) -> Page[JobView]:
        """Return jobs of one status. Ready, running, and blocked stay separate."""
        if status not in _JOB_STATUSES:
            raise ConsoleRefusal("status")
        chosen = tuple(job for job in self.jobs if job.status == status)
        return _page(chosen, cursor=cursor, limit=limit, identity=lambda item: item.job_id)

    def product_page(self, *, cursor: str | None = None, limit: int = 20) -> Page[ProductView]:
        """Return products in id order."""
        return _page(
            self.products, cursor=cursor, limit=limit, identity=lambda item: item.product_id
        )

    def variant_page(self, *, cursor: str | None = None, limit: int = 20) -> Page[VariantView]:
        """Return variants in id order."""
        return _page(
            self.variants, cursor=cursor, limit=limit, identity=lambda item: item.variant_id
        )

    def listing_page(self, *, cursor: str | None = None, limit: int = 20) -> Page[ListingView]:
        """Return listing state in id order."""
        return _page(
            self.listings, cursor=cursor, limit=limit, identity=lambda item: item.listing_id
        )

    def metric_page(self, *, cursor: str | None = None, limit: int = 20) -> Page[WeeklyMetricView]:
        """Return weekly metrics in week order."""
        return _page(
            self.weekly_metrics, cursor=cursor, limit=limit, identity=lambda item: item.week_start
        )

    def decision_page(self, *, cursor: str | None = None, limit: int = 20) -> Page[DecisionView]:
        """Return decisions in id order."""
        return _page(
            self.decisions, cursor=cursor, limit=limit, identity=lambda item: item.decision_id
        )

    def incident_page(self, *, cursor: str | None = None, limit: int = 20) -> Page[IncidentView]:
        """Return incidents in id order."""
        return _page(
            self.incidents, cursor=cursor, limit=limit, identity=lambda item: item.incident_id
        )

    def integration_page(
        self, *, cursor: str | None = None, limit: int = 20
    ) -> Page[IntegrationView]:
        """Return integration status in name order."""
        return _page(self.integrations, cursor=cursor, limit=limit, identity=lambda item: item.name)

    def milestone_page(self, *, cursor: str | None = None, limit: int = 20) -> Page[MilestoneView]:
        """Return milestone progress in name order."""
        return _page(self.milestones, cursor=cursor, limit=limit, identity=lambda item: item.name)

    def autonomy_settings(self) -> AutonomySettings:
        """Return the cap read. The values are not written here."""
        return self.autonomy

    def system_health(self) -> SystemHealth:
        """Derive health from the stored jobs."""
        running = sum(1 for job in self.jobs if job.status == "running")
        blocked = sum(1 for job in self.jobs if job.status == "blocked")
        return SystemHealth(running=running, blocked=blocked, action_required=blocked > 0)

    def _validate(self) -> None:
        if self.shop is not None:
            _text(self.shop.shop_id, "shop")
            _text(self.shop.name, "shop")
            _text(self.shop.currency, "shop")
        _unique(tuple(item.workflow_id for item in self.workflows), "workflow")
        workflow_ids = {item.workflow_id for item in self.workflows}
        for item in self.workflows:
            _text(item.workflow_id, "workflow")
            _text(item.name, "workflow")
            _text(item.stage, "workflow")
            _text(item.owning_agent, "workflow")
            _text(item.next_transition, "workflow")
            _count(item.elapsed_seconds, "workflow")
            if item.blocked_dependency is not None:
                _text(item.blocked_dependency, "workflow")
        _unique(tuple(item.stage for item in self.stages), "stage")
        for item in self.stages:
            _text(item.stage, "stage")
            _count(item.experiment_count, "stage")
        _unique(tuple(item.job_id for item in self.jobs), "job")
        for item in self.jobs:
            _text(item.job_id, "job")
            _text(item.job_type, "job")
            _count(item.attempt, "job")
            if item.status not in _JOB_STATUSES or item.workflow_id not in workflow_ids:
                raise ConsoleRefusal("job")
        _unique(tuple(item.product_id for item in self.products), "product")
        product_ids = {item.product_id for item in self.products}
        for item in self.products:
            _text(item.product_id, "product")
            _text(item.name, "product")
        _unique(tuple(item.variant_id for item in self.variants), "variant")
        for item in self.variants:
            _text(item.variant_id, "variant")
            _text(item.name, "variant")
            if item.product_id not in product_ids:
                raise ConsoleRefusal("variant")
        _unique(tuple(item.listing_id for item in self.listings), "listing")
        for item in self.listings:
            _text(item.listing_id, "listing")
            _text(item.decision, "listing")
            _text(item.next_review_at, "listing")
            _count(item.age_days, "listing")
            _count(item.views, "listing")
            _count(item.favourites, "listing")
            _count(item.sales, "listing")
            if item.state not in _LISTING_STATES or item.product_id not in product_ids:
                raise ConsoleRefusal("listing")
        _unique(tuple(item.week_start for item in self.weekly_metrics), "metric")
        for item in self.weekly_metrics:
            _text(item.week_start, "metric")
            _count(item.views, "metric")
            _count(item.favourites, "metric")
            _count(item.sales, "metric")
        _unique(tuple(item.decision_id for item in self.decisions), "decision")
        for item in self.decisions:
            _text(item.decision_id, "decision")
            _text(item.evidence, "decision")
            _text(item.status, "decision")
            if item.kind not in _DECISION_KINDS or not isinstance(_opaque(item.routine), bool):
                raise ConsoleRefusal("decision")
        _unique(tuple(item.incident_id for item in self.incidents), "incident")
        for item in self.incidents:
            _text(item.incident_id, "incident")
            _text(item.summary, "incident")
            _text(item.severity, "incident")
            _text(item.repair_step, "incident")
            _text(item.response_status, "incident")
        _unique(tuple(item.name for item in self.integrations), "integration")
        for item in self.integrations:
            _text(item.name, "integration")
            if item.status not in _INTEGRATION_STATES:
                raise ConsoleRefusal("integration")
        _unique(tuple(item.name for item in self.milestones), "milestone")
        for item in self.milestones:
            _text(item.name, "milestone")
            _count(item.completed, "milestone")
            _count(item.total, "milestone")
            if item.completed > item.total:
                raise ConsoleRefusal("milestone")
        settings = self.autonomy
        _text(settings.mode, "autonomy")
        _count(settings.publication_cap, "autonomy")
        _count(settings.purchase_cap, "autonomy")
        _count(settings.loop_day, "autonomy")
        if settings.posthog != "offline" or settings.provider != "unread":
            raise ConsoleRefusal("autonomy")
