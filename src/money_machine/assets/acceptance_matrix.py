"""Record the definition-of-done matrix from the code that actually runs.

Each of the twenty-five items is ``PASS``, ``FAIL``, or ``BLOCKED_EXTERNAL``.
A live item with no live call stays blocked. A ``FAIL`` is not a pass.
The handover cites those rows and does not contain the exit string.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Never

from money_machine.assets.failure_injection import run_failure_injections
from money_machine.assets.implementation_matrix import MatrixRow, MatrixStatus, build_matrix
from money_machine.assets.linked_workflow import (
    LinkedWorkflowRefusal,
    advance_linked_workflow,
    run_linked_workflow,
)
from money_machine.config.loader import load_yaml_model
from money_machine.config.settings import AgentsConfig

_EXIT_STRINGS = (
    "HANDS_OFF_MONEY_MACHINE_COMMISSIONED",
    "SESSION_14_PRODUCTION_DEPLOYMENT_COMPLETE",
)
_DEFINITIONS: tuple[tuple[int, str, str], ...] = (
    (1, "private_repository", "live"),
    (2, "local_setup", "check"),
    (3, "postgresql_source_of_truth", "live"),
    (4, "orchestrator_restart", "check"),
    (5, "agents_commissioned", "check"),
    (6, "agent_contracts", "check"),
    (7, "playbook_ownership", "check"),
    (8, "successor_links", "check"),
    (9, "notion_product", "live"),
    (10, "variants_and_secret_links", "check"),
    (11, "generated_assets", "check"),
    (12, "etsy_drafts", "check"),
    (13, "preflight_guard", "check"),
    (14, "live_publication", "live"),
    (15, "metrics_and_maturity", "check"),
    (16, "automatic_cull", "live"),
    (17, "multiplication", "check"),
    (18, "incident_repair", "check"),
    (19, "operator_console", "check"),
    (20, "posthog", "live"),
    (21, "e2e_and_failure_injection", "check"),
    (22, "production_deploy_and_backup", "live"),
    (23, "live_credentials", "live"),
    (24, "real_workflow", "live"),
    (25, "documentation_matches", "check"),
)
_LIVE_EVIDENCE = {
    "private_repository": "repository privacy is an account setting",
    "postgresql_source_of_truth": "live postgres is not opened",
    "notion_product": "live notion is not called",
    "live_publication": "publish stays refused",
    "automatic_cull": "live deactivation is not called",
    "posthog": "live posthog is not called",
    "production_deploy_and_backup": "live deploy is not run",
    "live_credentials": "no credential is read",
    "real_workflow": "the fixture chain stops at preflight",
}


class Verdict(StrEnum):
    """The three marks the acceptance matrix allows."""

    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED_EXTERNAL = "BLOCKED_EXTERNAL"


class AcceptanceMatrixRefusal(ValueError):
    """The matrix omitted an item, passed a live item, or wrote the exit string."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class AcceptanceItem:
    """One definition-of-done row."""

    number: int
    name: str
    verdict: Verdict
    evidence: str


@dataclass(frozen=True, slots=True)
class AcceptanceMatrix:
    """The twenty-five rows and the handover that cites them."""

    items: tuple[AcceptanceItem, ...]
    handover: str
    live_call: bool


def record_acceptance_matrix(root: Path | None = None) -> AcceptanceMatrix:
    """Score every definition item. This function does not make a live call."""
    repository = Path(__file__).resolve().parents[3] if root is None else root
    items = _items(repository)
    validate_acceptance(items)
    handover = render_handover(items)
    refuse_exit_string(handover)
    return AcceptanceMatrix(items=items, handover=handover, live_call=False)


def accept_page(page: str) -> None:
    """A handover page does not earn the evidence key."""
    del page
    raise AcceptanceMatrixRefusal("page")


def counts_as_pass(verdict: Verdict) -> bool:
    """Only ``PASS`` counts. ``FAIL`` and ``BLOCKED_EXTERNAL`` do not."""
    if verdict is Verdict.PASS:
        return True
    if verdict is Verdict.FAIL or verdict is Verdict.BLOCKED_EXTERNAL:
        return False
    return _unexpected(verdict)


def validate_acceptance(items: tuple[AcceptanceItem, ...]) -> None:
    """Refuse a missing row, a live pass, or a failure counted as a pass."""
    expected = [name for _number, name, _kind in _DEFINITIONS]
    if [item.name for item in items] != expected or len(items) != 25:
        raise AcceptanceMatrixRefusal("omitted")
    live = {name for _number, name, kind in _DEFINITIONS if kind == "live"}
    for item in items:
        if item.verdict not in {Verdict.PASS, Verdict.FAIL, Verdict.BLOCKED_EXTERNAL}:
            raise AcceptanceMatrixRefusal("verdict")
        if item.name in live and item.verdict is not Verdict.BLOCKED_EXTERNAL:
            raise AcceptanceMatrixRefusal("live_item")
        if item.verdict is Verdict.FAIL and counts_as_pass(item.verdict):
            raise AcceptanceMatrixRefusal("fail_as_pass")


def render_handover(items: tuple[AcceptanceItem, ...]) -> str:
    """Cite every row that is not a pass. The exit string is not written."""
    lines = ["Acceptance handover.", "The exit string is not written."]
    for item in items:
        if item.verdict is not Verdict.PASS:
            lines.append(f"{item.number}. {item.name}: {item.verdict.value}. {item.evidence}.")
    return "\n".join(lines) + "\n"


def refuse_exit_string(text: str) -> None:
    """Refuse either commissioning exit string."""
    if any(token in text for token in _EXIT_STRINGS):
        raise AcceptanceMatrixRefusal("exit_string")


def _items(root: Path) -> tuple[AcceptanceItem, ...]:
    scored = _score(root)
    rows: list[AcceptanceItem] = []
    for number, name, kind in _DEFINITIONS:
        if kind == "live":
            verdict, evidence = Verdict.BLOCKED_EXTERNAL, _LIVE_EVIDENCE[name]
        else:
            verdict, evidence = scored[name]
        rows.append(AcceptanceItem(number, name, verdict, evidence))
    return tuple(rows)


def _score(root: Path) -> dict[str, tuple[Verdict, str]]:
    matrix = build_matrix(root)
    linked = run_linked_workflow()
    injections = run_failure_injections()
    agents = load_yaml_model(root / "config" / "agents.yaml", AgentsConfig)
    state_path = root / "docs" / "control" / "IMPLEMENTATION_STATE.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    commissioned = state.get("commissioned_agents")
    by_step = {row.name: row for row in matrix if row.surface == "playbook_step"}
    views = [row for row in matrix if row.surface == "console_view"]
    recovered = {
        item.name
        for item in injections
        if item.disposition == "RECOVERED" and item.name in {"worker_crash", "scheduler_restart"}
    }
    publish_refused = False
    try:
        advance_linked_workflow("publish", enabled=True)
    except LinkedWorkflowRefusal as error:
        publish_refused = error.code == "publish"
    return {
        "local_setup": (Verdict.FAIL, "dual_shell_not_executed"),
        "orchestrator_restart": _recovered(recovered),
        "agents_commissioned": _commissioned(commissioned),
        "agent_contracts": _contracts(agents),
        "playbook_ownership": _owned(by_step),
        "successor_links": _present(by_step, "successor_product_spec"),
        "variants_and_secret_links": _variants(by_step, root),
        "generated_assets": _both(by_step, "assets", "pdfs"),
        "etsy_drafts": _present(by_step, "etsy_draft"),
        "preflight_guard": _preflight(linked.stopped_at, publish_refused),
        "metrics_and_maturity": _both(by_step, "weekly_metrics", "thirty_day_maturity"),
        "multiplication": (Verdict.FAIL, "successor_build_withheld"),
        "incident_repair": _present(by_step, "repair"),
        "operator_console": _views(views),
        "e2e_and_failure_injection": _e2e(len(injections), linked.stopped_at),
        "documentation_matches": _documentation(root),
    }


def _recovered(names: set[str]) -> tuple[Verdict, str]:
    if names == {"worker_crash", "scheduler_restart"}:
        return Verdict.PASS, "failure_injection.restart"
    return Verdict.FAIL, "restart_not_recovered"


def _commissioned(value: object) -> tuple[Verdict, str]:
    if isinstance(value, list) and len(value) == 16:
        return Verdict.PASS, "commissioned_agents"
    return Verdict.FAIL, "commissioned_agents_empty"


def _contracts(agents: AgentsConfig) -> tuple[Verdict, str]:
    versioned = [
        agent
        for agent in agents.agents
        if agent.contract_version >= 1 and agent.implementation_version >= 1
    ]
    if len(agents.agents) == 16 and len(versioned) == 16:
        return Verdict.PASS, "config/agents.yaml"
    return Verdict.FAIL, "agent_contracts"


def _owned(steps: dict[str, MatrixRow]) -> tuple[Verdict, str]:
    missing = [name for name, row in steps.items() if row.status is MatrixStatus.MISSING]
    if steps and not missing:
        return Verdict.PASS, "implementation_matrix.playbook"
    return Verdict.FAIL, "playbook_missing"


def _variants(steps: dict[str, MatrixRow], root: Path) -> tuple[Verdict, str]:
    present = _present(steps, "variants")
    secret = root / "src/money_machine/integrations/notion/publishing.py"
    if present[0] is Verdict.PASS and secret.is_file():
        return Verdict.PASS, "variants+secret_link"
    return Verdict.FAIL, "variants_and_secret_links"


def _present(steps: dict[str, MatrixRow], name: str) -> tuple[Verdict, str]:
    row = steps.get(name)
    if row is not None and row.status is not MatrixStatus.MISSING:
        return Verdict.PASS, row.evidence
    return Verdict.FAIL, name


def _both(steps: dict[str, MatrixRow], left: str, right: str) -> tuple[Verdict, str]:
    first = _present(steps, left)
    second = _present(steps, right)
    if first[0] is Verdict.PASS and second[0] is Verdict.PASS:
        return Verdict.PASS, f"{left}+{right}"
    return Verdict.FAIL, f"{left}+{right}"


def _preflight(stopped_at: str, publish_refused: bool) -> tuple[Verdict, str]:
    if stopped_at == "preflight" and publish_refused:
        return Verdict.PASS, "linked_workflow.preflight"
    return Verdict.FAIL, "preflight"


def _views(rows: list[MatrixRow]) -> tuple[Verdict, str]:
    if rows and all(row.status is MatrixStatus.IMPLEMENTED_AND_TESTED for row in rows):
        return Verdict.PASS, "operator_views"
    return Verdict.FAIL, "operator_console"


def _e2e(count: int, stopped_at: str) -> tuple[Verdict, str]:
    if count == 18 and stopped_at == "preflight":
        return Verdict.PASS, "failure_injection+linked_workflow"
    return Verdict.FAIL, "e2e"


def _documentation(root: Path) -> tuple[Verdict, str]:
    # session_evidence imports state, and state imports the Session 15 proof.
    from money_machine.control.session_evidence import render_session_evidence

    catalogue = root / "docs" / "control" / "SESSION_EVIDENCE.md"
    if catalogue.is_file() and catalogue.read_text(encoding="utf-8") == render_session_evidence():
        return Verdict.PASS, "SESSION_EVIDENCE.md"
    return Verdict.FAIL, "catalogue"


def _unexpected(verdict: Verdict) -> Never:
    raise AcceptanceMatrixRefusal(verdict.value)
