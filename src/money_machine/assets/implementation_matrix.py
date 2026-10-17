"""Classify the running system without calling a provider.

Each row is one of four statuses. A live credential gap stays blocked.
A fail-closed agent stays missing. The matrix does not open a socket.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from money_machine.agents.base import AgentNotImplementedError
from money_machine.agents.registry import AgentRegistry
from money_machine.assets.operator_views import ConsoleViews
from money_machine.config.loader import load_yaml_model
from money_machine.config.settings import AgentsConfig, SideEffectClass, WorkflowsConfig
from money_machine.domain.enums import JobStatus, ProductLifecycleState
from money_machine.domain.events import EventName, TelemetryEventName
from money_machine.orchestration.transition_guard import JOB_TRANSITIONS, PRODUCT_TRANSITIONS

_SURFACES = (
    "playbook_step",
    "job_type",
    "event",
    "lifecycle_transition",
    "agent",
    "provider_action",
    "console_view",
    "runbook",
)
_BLOCKED_EFFECTS = frozenset(
    {
        SideEffectClass.EXTERNAL_READ,
        SideEffectClass.EXTERNAL_WRITE,
        SideEffectClass.EXTERNAL_SPEND,
        SideEffectClass.EXTERNAL_MESSAGE,
    }
)
_BLOCKED_JOBS = frozenset(
    {
        "PublishListingJob",
        "CompetitorPurchaseJob",
        "ProofDistributionJob",
    }
)
_TESTED_PATHS = frozenset(
    {
        "src/money_machine/assets/closed_loop_store.py",
        "src/money_machine/assets/etsy_preflight.py",
        "src/money_machine/assets/maturity_clock.py",
        "src/money_machine/assets/metrics_fixture.py",
        "src/money_machine/assets/operator_views.py",
        "src/money_machine/assets/portfolio_eligibility.py",
        "src/money_machine/assets/support_intake.py",
    }
)
_RUNBOOKS = (
    "backup_restore",
    "database_reconnect",
    "duplicate_publish",
    "scheduler_restart",
    "worker_crash",
)
_SECRET_MARKERS = ("sk_", "bearer ", "cookie=", ".env")


class MatrixStatus(StrEnum):
    """The four classifications the Session 13 contract allows."""

    IMPLEMENTED_AND_TESTED = "IMPLEMENTED_AND_TESTED"
    IMPLEMENTED_NOT_LIVE_TESTED = "IMPLEMENTED_NOT_LIVE_TESTED"
    BLOCKED_BY_EXTERNAL_CREDENTIAL = "BLOCKED_BY_EXTERNAL_CREDENTIAL"
    MISSING = "MISSING"


class MatrixRefusal(ValueError):
    """The matrix hid a gap or named a row twice."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class MatrixRow:
    """One classified surface. ``evidence`` is a path or a short reason."""

    surface: str
    name: str
    status: MatrixStatus
    evidence: str


@dataclass(frozen=True, slots=True)
class _PlaybookStep:
    name: str
    evidence: str
    blocked: bool = False


_PLAYBOOK = (
    _PlaybookStep("research", "src/money_machine/agents/implementations/market_research.py"),
    _PlaybookStep("shortlist", "src/money_machine/agents/implementations/market_research.py"),
    _PlaybookStep("score", "src/money_machine/agents/implementations/product_strategy.py"),
    _PlaybookStep("teardown", "src/money_machine/agents/implementations/competitor_teardown.py"),
    _PlaybookStep("product_spec", "src/money_machine/agents/implementations/product_strategy.py"),
    _PlaybookStep("dedupe", "src/money_machine/agents/implementations/catalogue_dedupe.py"),
    _PlaybookStep(
        "notion_build",
        "src/money_machine/agents/implementations/notion_product_builder.py",
    ),
    _PlaybookStep("qa", "src/money_machine/agents/implementations/product_qa.py"),
    _PlaybookStep("variants", "src/money_machine/agents/implementations/variant_builder.py"),
    _PlaybookStep("listing_copy", "src/money_machine/agents/implementations/merchandising.py"),
    _PlaybookStep("assets", "src/money_machine/agents/implementations/creative_assets.py"),
    _PlaybookStep("pdfs", "src/money_machine/assets/delivery_pdfs.py"),
    _PlaybookStep("etsy_draft", "src/money_machine/integrations/etsy/draft_client.py"),
    _PlaybookStep("preflight", "src/money_machine/assets/etsy_preflight.py"),
    _PlaybookStep(
        "publish_simulation",
        "src/money_machine/agents/implementations/etsy_publishing.py",
        True,
    ),
    _PlaybookStep(
        "post_publish_verification",
        "src/money_machine/agents/implementations/etsy_publishing.py",
        True,
    ),
    _PlaybookStep("weekly_metrics", "src/money_machine/assets/metrics_fixture.py"),
    _PlaybookStep("thirty_day_maturity", "src/money_machine/assets/maturity_clock.py"),
    _PlaybookStep("winner", "src/money_machine/assets/portfolio_eligibility.py"),
    _PlaybookStep("successor_product_spec", "src/money_machine/orchestration/successor_factory.py"),
    _PlaybookStep("successor_build_job", "src/money_machine/orchestration/successor_factory.py"),
    _PlaybookStep("cull", "src/money_machine/assets/closed_loop_store.py"),
    _PlaybookStep("repair", "src/money_machine/assets/support_intake.py"),
    _PlaybookStep("broken_link", "src/money_machine/assets/support_intake.py"),
)


def build_matrix(root: Path | None = None) -> tuple[MatrixRow, ...]:
    """Read the repository and return one row per required surface."""
    repository = Path(__file__).resolve().parents[3] if root is None else root
    rows = (
        *_playbook_rows(repository),
        *_job_rows(repository),
        *_event_rows(),
        *_lifecycle_rows(),
        *_agent_rows(repository),
        *_provider_rows(repository),
        *_view_rows(),
        *_runbook_rows(),
    )
    validate_matrix(rows, repository)
    return rows


def validate_matrix(rows: tuple[MatrixRow, ...], root: Path) -> None:
    """Refuse a duplicate, a live gap marked tested, or a missing required surface."""
    seen: set[tuple[str, str]] = set()
    by_surface: dict[str, set[str]] = {surface: set() for surface in _SURFACES}
    for row in rows:
        if row.surface not in _SURFACES:
            raise MatrixRefusal("surface")
        identity = (row.surface, row.name)
        if identity in seen:
            raise MatrixRefusal("duplicate")
        seen.add(identity)
        by_surface[row.surface].add(row.name)
        folded = f"{row.name} {row.evidence}".casefold()
        if any(marker in folded for marker in _SECRET_MARKERS):
            raise MatrixRefusal("secret")
        tested = row.status is MatrixStatus.IMPLEMENTED_AND_TESTED
        if tested and not (root / row.evidence).is_file():
            raise MatrixRefusal("tested_path")
        blocked = row.status is MatrixStatus.BLOCKED_BY_EXTERNAL_CREDENTIAL
        if row.name in _BLOCKED_JOBS and not blocked:
            raise MatrixRefusal("blocked_job")
        publish = row.name in {"publish_simulation", "post_publish_verification"}
        if row.surface == "playbook_step" and publish and not blocked:
            raise MatrixRefusal("blocked_playbook")
    if any(not names for names in by_surface.values()):
        raise MatrixRefusal("empty_surface")
    _require_coverage(by_surface, root)


def _require_coverage(by_surface: dict[str, set[str]], root: Path) -> None:
    workflows = load_yaml_model(root / "config" / "workflows.yaml", WorkflowsConfig)
    job_names = {job.job_type for workflow in workflows.workflows for job in workflow.jobs}
    event_names = {item.value for item in EventName} | {item.value for item in TelemetryEventName}
    product_names = {f"product:{item.value}" for item in ProductLifecycleState}
    job_states = {f"job:{item.value}" for item in JobStatus}
    agents = {f"A{number:02d}" for number in range(1, 17)}
    views = {field.name for field in ConsoleViews.__dataclass_fields__.values()}
    if by_surface["job_type"] != job_names:
        raise MatrixRefusal("job_coverage")
    if by_surface["event"] != event_names:
        raise MatrixRefusal("event_coverage")
    if by_surface["lifecycle_transition"] != product_names | job_states:
        raise MatrixRefusal("lifecycle_coverage")
    if by_surface["agent"] != agents:
        raise MatrixRefusal("agent_coverage")
    if by_surface["console_view"] != views:
        raise MatrixRefusal("view_coverage")
    if by_surface["runbook"] != set(_RUNBOOKS):
        raise MatrixRefusal("runbook_coverage")


def _row(surface: str, name: str, status: MatrixStatus, evidence: str) -> MatrixRow:
    return MatrixRow(surface=surface, name=name, status=status, evidence=evidence)


def _playbook_rows(root: Path) -> tuple[MatrixRow, ...]:
    rows: list[MatrixRow] = []
    for step in _PLAYBOOK:
        if step.blocked:
            status = MatrixStatus.BLOCKED_BY_EXTERNAL_CREDENTIAL
        elif not (root / step.evidence).is_file():
            status = MatrixStatus.MISSING
        elif step.evidence in _TESTED_PATHS:
            status = MatrixStatus.IMPLEMENTED_AND_TESTED
        else:
            status = MatrixStatus.IMPLEMENTED_NOT_LIVE_TESTED
        rows.append(_row("playbook_step", step.name, status, step.evidence))
    return tuple(rows)


def _job_rows(root: Path) -> tuple[MatrixRow, ...]:
    workflows = load_yaml_model(root / "config" / "workflows.yaml", WorkflowsConfig)
    rows: list[MatrixRow] = []
    for workflow in workflows.workflows:
        for job in workflow.jobs:
            blocked = job.side_effect_class in _BLOCKED_EFFECTS or job.job_type in _BLOCKED_JOBS
            status = (
                MatrixStatus.BLOCKED_BY_EXTERNAL_CREDENTIAL
                if blocked
                else MatrixStatus.IMPLEMENTED_NOT_LIVE_TESTED
            )
            rows.append(_row("job_type", job.job_type, status, workflow.workflow_type))
    return tuple(rows)


def _event_rows() -> tuple[MatrixRow, ...]:
    events_path = "src/money_machine/domain/events.py"
    durable = tuple(
        _row("event", item.value, MatrixStatus.IMPLEMENTED_AND_TESTED, events_path)
        for item in EventName
    )
    telemetry = tuple(
        _row(
            "event",
            item.value,
            MatrixStatus.IMPLEMENTED_NOT_LIVE_TESTED,
            "domain.events.TelemetryEventName",
        )
        for item in TelemetryEventName
    )
    return durable + telemetry


def _lifecycle_rows() -> tuple[MatrixRow, ...]:
    product = tuple(
        _row(
            "lifecycle_transition",
            f"product:{state.value}",
            MatrixStatus.IMPLEMENTED_AND_TESTED,
            "src/money_machine/orchestration/transition_guard.py",
        )
        for state in PRODUCT_TRANSITIONS
    )
    jobs = tuple(
        _row(
            "lifecycle_transition",
            f"job:{state.value}",
            MatrixStatus.IMPLEMENTED_AND_TESTED,
            "src/money_machine/orchestration/transition_guard.py",
        )
        for state in JOB_TRANSITIONS
    )
    return product + jobs


def _agent_rows(root: Path) -> tuple[MatrixRow, ...]:
    registry = AgentRegistry.from_yaml(root)
    rows: list[MatrixRow] = []
    for definition in registry.roster():
        try:
            registry.get_implementation(definition.agent_id)
        except AgentNotImplementedError:
            status = MatrixStatus.MISSING
            evidence = "registry raises AgentNotImplementedError"
        else:
            status = MatrixStatus.IMPLEMENTED_NOT_LIVE_TESTED
            evidence = "agents.registry.AgentRegistry"
        rows.append(_row("agent", definition.agent_id, status, evidence))
    return tuple(rows)


def _provider_rows(root: Path) -> tuple[MatrixRow, ...]:
    agents = load_yaml_model(root / "config" / "agents.yaml", AgentsConfig)
    workflows = load_yaml_model(root / "config" / "workflows.yaml", WorkflowsConfig)
    names = {operation for agent in agents.agents for operation in agent.provider_operations}
    names.update(
        job.capability_operation
        for workflow in workflows.workflows
        for job in workflow.jobs
        if job.capability_operation is not None
    )
    return tuple(
        _row(
            "provider_action",
            name,
            MatrixStatus.BLOCKED_BY_EXTERNAL_CREDENTIAL,
            "config provider operation",
        )
        for name in sorted(names)
    )


def _view_rows() -> tuple[MatrixRow, ...]:
    return tuple(
        _row(
            "console_view",
            field.name,
            MatrixStatus.IMPLEMENTED_AND_TESTED,
            "src/money_machine/assets/operator_views.py",
        )
        for field in ConsoleViews.__dataclass_fields__.values()
    )


def _runbook_rows() -> tuple[MatrixRow, ...]:
    return tuple(
        _row("runbook", name, MatrixStatus.MISSING, "no runbook module") for name in _RUNBOOKS
    )
