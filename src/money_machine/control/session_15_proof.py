"""Earn the Session 15 deployed-state, provider, authority, and workflow keys.

The proof calls the deployed-state check, the fixture provider selector, the
standing-authority check, the linked workflow, and the acceptance matrix.
The workflow stops at preflight. A live matrix item stays blocked. A failure
is not a pass. The closure key stays false.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

from money_machine.assets.acceptance_matrix import (
    AcceptanceMatrixRefusal,
    Verdict,
    accept_page,
    counts_as_pass,
    record_acceptance_matrix,
    refuse_exit_string,
)
from money_machine.assets.linked_workflow import (
    LinkedWorkflowRefusal,
    advance_linked_workflow,
    run_linked_workflow,
)
from money_machine.config.loader import load_yaml_model
from money_machine.config.settings import AutonomyConfig
from money_machine.config.standing_authority import (
    StandingAuthorityRefusal,
    record_standing_authority,
)
from money_machine.deploy.checkpoint import CheckpointRefusal
from money_machine.deploy.deployed_state import DeployedStateRefusal, check_deployed_state
from money_machine.domain.enums import AutonomyMode
from money_machine.integrations.provider_connections import (
    ProviderConnectionRefusal,
    select_provider_connections,
)

DEPLOYED_STATE_KEY = "deployed_state_checked"
PROVIDER_CONNECTIONS_KEY = "provider_connections_fail_closed"
STANDING_AUTHORITY_KEY = "standing_authority_recorded"
LINKED_WORKFLOW_KEY = "linked_workflow_fixture"
ACCEPTANCE_MATRIX_KEY = "acceptance_matrix_recorded"
EARNED_EVIDENCE_KEYS = frozenset(
    {
        DEPLOYED_STATE_KEY,
        PROVIDER_CONNECTIONS_KEY,
        STANDING_AUTHORITY_KEY,
        LINKED_WORKFLOW_KEY,
        ACCEPTANCE_MATRIX_KEY,
    }
)
_CLOSURE_HEAD = "02c26f39ac8800db03ae7f5d1d346487a5ce123e"
_POINTER_REVISION = 117
_UPDATED_AT = "2026-10-17T16:35:00Z"
_TRUE_KEYS: frozenset[str] = frozenset(
    {
        DEPLOYED_STATE_KEY,
        PROVIDER_CONNECTIONS_KEY,
        STANDING_AUTHORITY_KEY,
        LINKED_WORKFLOW_KEY,
        ACCEPTANCE_MATRIX_KEY,
    }
)
_MODULE = Path(__file__).resolve().parents[1] / "deploy" / "deployed_state.py"
_CONNECTIONS = Path(__file__).resolve().parents[1] / "integrations" / "provider_connections.py"
_AUTHORITY = Path(__file__).resolve().parents[1] / "config" / "standing_authority.py"
_WORKFLOW = Path(__file__).resolve().parents[1] / "assets" / "linked_workflow.py"
_MATRIX = Path(__file__).resolve().parents[1] / "assets" / "acceptance_matrix.py"
_WORKER = Path("src/money_machine/orchestration/worker.py")
_SCHEDULER = Path("src/money_machine/orchestration/scheduler.py")


class Session15ProofError(ValueError):
    """The deployed-state check did not earn its evidence key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def prove_session_15() -> frozenset[str]:
    """Return the earned Session 15 keys. A miss raises instead of returning them."""
    _prove_deployed_state()
    _prove_provider_connections()
    _prove_standing_authority()
    _prove_linked_workflow()
    _prove_acceptance_matrix()
    return EARNED_EVIDENCE_KEYS


def session_15_pointer_holds(evidence: object) -> bool:
    """The live Session 15 keys match the set this proof has earned."""
    if not isinstance(evidence, dict):
        return False
    for key, value in evidence.items():
        if not isinstance(key, str) or not isinstance(value, bool):
            return False
        expected = key in EARNED_EVIDENCE_KEYS
        if value is not expected:
            return False
    return True


def _prove_deployed_state() -> None:
    _refuse_network(_MODULE)
    root = Path(__file__).resolve().parents[3]
    before = {relative: (root / relative).read_bytes() for relative in (_WORKER, _SCHEDULER)}
    try:
        checked = check_deployed_state(
            expected_revision=_POINTER_REVISION,
            expected_updated_at=_UPDATED_AT,
            expected_true_keys=_TRUE_KEYS,
            closure_head=_CLOSURE_HEAD,
        )
    except (DeployedStateRefusal, CheckpointRefusal) as error:
        raise Session15ProofError(error.code) from error
    if {relative: (root / relative).read_bytes() for relative in before} != before:
        raise Session15ProofError("sources_edited")
    if (
        checked.revision != _POINTER_REVISION
        or checked.updated_at != _UPDATED_AT
        or checked.head_sha != _CLOSURE_HEAD
        or checked.true_keys != tuple(sorted(_TRUE_KEYS))
        or checked.smoke_ran is not False
        or checked.services_started is not False
        or checked.exit_78_held is not True
    ):
        raise Session15ProofError("deployed_state")
    _require_refusal(
        lambda: check_deployed_state(
            expected_revision=_POINTER_REVISION,
            expected_updated_at=_UPDATED_AT,
            expected_true_keys=_TRUE_KEYS,
            closure_head=_CLOSURE_HEAD,
            live_smoke=True,
        ),
        "live_smoke",
    )
    _require_refusal(
        lambda: check_deployed_state(
            expected_revision=_POINTER_REVISION,
            expected_updated_at=_UPDATED_AT,
            expected_true_keys=_TRUE_KEYS,
            closure_head=_CLOSURE_HEAD,
            docker_socket=True,
        ),
        "docker_socket",
    )
    _require_refusal(
        lambda: check_deployed_state(
            expected_revision=_POINTER_REVISION,
            expected_updated_at=_UPDATED_AT,
            expected_true_keys=_TRUE_KEYS,
            closure_head=_CLOSURE_HEAD,
            start_services=True,
        ),
        "service_start",
    )


def _prove_provider_connections() -> None:
    """The fixture adapters are selected. A live adapter raises and is not constructed."""
    _refuse_network(_CONNECTIONS)
    root = Path(__file__).resolve().parents[3]
    before = {relative: (root / relative).read_bytes() for relative in (_WORKER, _SCHEDULER)}
    try:
        selected = select_provider_connections()
    except ProviderConnectionRefusal as error:
        raise Session15ProofError(error.code) from error
    if {relative: (root / relative).read_bytes() for relative in before} != before:
        raise Session15ProofError("sources_edited")
    if (
        selected.etsy != "fixture"
        or selected.notion != "fixture"
        or selected.listing_count < 1
        or selected.notion_connected is not True
        or selected.live_call is not False
        or selected.credential_read is not False
    ):
        raise Session15ProofError("provider_connections")
    for mode in ("api", "browser", "combined", "live", ""):
        _require_provider_refusal(
            lambda mode=mode: select_provider_connections(etsy_mode=mode),
            "live_etsy",
        )
        _require_provider_refusal(
            lambda mode=mode: select_provider_connections(notion_mode=mode),
            "live_notion",
        )


def _prove_standing_authority() -> None:
    """The template keeps publish, purchase, and checkout false."""
    _refuse_network(_AUTHORITY)
    root = Path(__file__).resolve().parents[3]
    before = {relative: (root / relative).read_bytes() for relative in (_WORKER, _SCHEDULER)}
    try:
        recorded = record_standing_authority()
    except StandingAuthorityRefusal as error:
        raise Session15ProofError(error.code) from error
    if {relative: (root / relative).read_bytes() for relative in before} != before:
        raise Session15ProofError("sources_edited")
    if (
        recorded.auto_publish is not False
        or recorded.auto_deactivate is not False
        or recorded.auto_multiply is not False
        or recorded.competitor_purchase_enabled is not False
        or recorded.live_checkout_test_enabled is not False
        or any(cap > 0 for cap in recorded.purchase_caps)
        or recorded.checkout_cap > 0
    ):
        raise Session15ProofError("standing_authority")
    _require_authority_refusal(_live(auto_publish=True), "publish")
    _require_authority_refusal(_live(auto_deactivate=True), "deactivate")
    _require_authority_refusal(_live(auto_multiply=True), "multiply")
    _require_authority_refusal(
        _live(
            competitor_purchase_enabled=True,
            competitor_purchase_max_each="1.00",
            competitor_purchase_monthly_cap="5.00",
            external_spend_enabled=True,
        ),
        "purchase",
    )
    _require_authority_refusal(
        _live(
            live_checkout_test_enabled=True,
            live_checkout_test_cap="1.00",
            external_spend_enabled=True,
        ),
        "checkout",
    )
    _require_authority_refusal(_live(), "live_authority")


def _live(**overrides: object) -> AutonomyConfig:
    root = Path(__file__).resolve().parents[3]
    template = load_yaml_model(root / "config" / "autonomy.example.yaml", AutonomyConfig)
    values = template.model_dump()
    values.update(
        {
            "mode": AutonomyMode.LIVE,
            "external_mutations_enabled": True,
        }
    )
    values.update(overrides)
    return AutonomyConfig.model_validate(values)


def _prove_linked_workflow() -> None:
    """The fixture chain stops at preflight. A true flag does not continue."""
    _refuse_network(_WORKFLOW)
    root = Path(__file__).resolve().parents[3]
    before = {relative: (root / relative).read_bytes() for relative in (_WORKER, _SCHEDULER)}
    try:
        recorded = run_linked_workflow()
    except LinkedWorkflowRefusal as error:
        raise Session15ProofError(error.code) from error
    if {relative: (root / relative).read_bytes() for relative in before} != before:
        raise Session15ProofError("sources_edited")
    if (
        recorded.stopped_at != "preflight"
        or recorded.provider != "fixture"
        or recorded.listing_count < 1
        or recorded.notion_connected is not True
        or recorded.preflight_passed is not True
        or recorded.published is not False
        or recorded.purchased is not False
        or recorded.checkout is not False
    ):
        raise Session15ProofError("linked_workflow")
    for action in ("publish", "purchase", "checkout"):
        _require_workflow_refusal(action, enabled=True)
        _require_workflow_refusal(action, enabled=False)


def _prove_acceptance_matrix() -> None:
    """Every definition item is marked. A live item stays blocked. A page is not a key."""
    _refuse_network(_MATRIX)
    root = Path(__file__).resolve().parents[3]
    before = {relative: (root / relative).read_bytes() for relative in (_WORKER, _SCHEDULER)}
    try:
        recorded = record_acceptance_matrix()
    except AcceptanceMatrixRefusal as error:
        raise Session15ProofError(error.code) from error
    if {relative: (root / relative).read_bytes() for relative in before} != before:
        raise Session15ProofError("sources_edited")
    live = {
        "private_repository",
        "postgresql_source_of_truth",
        "notion_product",
        "live_publication",
        "automatic_cull",
        "posthog",
        "production_deploy_and_backup",
        "live_credentials",
        "real_workflow",
    }
    names = [item.name for item in recorded.items]
    if (
        len(recorded.items) != 25
        or len(set(names)) != 25
        or recorded.live_call is not False
        or any(
            item.verdict not in {Verdict.PASS, Verdict.FAIL, Verdict.BLOCKED_EXTERNAL}
            for item in recorded.items
        )
        or any(
            item.verdict is not Verdict.BLOCKED_EXTERNAL
            for item in recorded.items
            if item.name in live
        )
        or not any(item.verdict is Verdict.FAIL for item in recorded.items)
        or any(
            counts_as_pass(item.verdict) for item in recorded.items if item.verdict is Verdict.FAIL
        )
    ):
        raise Session15ProofError("acceptance_matrix")
    try:
        refuse_exit_string(recorded.handover)
    except AcceptanceMatrixRefusal as error:
        raise Session15ProofError(error.code) from error
    try:
        accept_page(recorded.handover)
    except AcceptanceMatrixRefusal as error:
        if error.code != "page":
            raise Session15ProofError("page") from error
    else:
        raise Session15ProofError("page")


def _require_workflow_refusal(action: str, *, enabled: bool) -> None:
    try:
        if action == "publish":
            advance_linked_workflow("publish", enabled=enabled)
        elif action == "purchase":
            advance_linked_workflow("purchase", enabled=enabled)
        elif action == "checkout":
            advance_linked_workflow("checkout", enabled=enabled)
        else:
            raise Session15ProofError(action)
    except LinkedWorkflowRefusal as error:
        if error.code != action:
            raise Session15ProofError(action) from error
    else:
        raise Session15ProofError(action)


def _require_authority_refusal(authority: AutonomyConfig, code: str) -> None:
    try:
        record_standing_authority(authority)
    except StandingAuthorityRefusal as error:
        if error.code != code:
            raise Session15ProofError(code) from error
    else:
        raise Session15ProofError(code)


def _require_provider_refusal(call: Callable[[], object], code: str) -> None:
    try:
        call()
    except ProviderConnectionRefusal as error:
        if error.code != code:
            raise Session15ProofError(code) from error
    else:
        raise Session15ProofError(code)


def _require_refusal(call: Callable[[], object], code: str) -> None:
    try:
        call()
    except DeployedStateRefusal as error:
        if error.code != code:
            raise Session15ProofError(code) from error
    else:
        raise Session15ProofError(code)


def _refuse_network(module: Path) -> None:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    folded = " ".join(imported)
    banned = ("socket", "httpx", "urllib", "requests", "dotenv", "subprocess", "docker")
    if any(token in folded for token in banned):
        raise Session15ProofError("deployed_socket")
