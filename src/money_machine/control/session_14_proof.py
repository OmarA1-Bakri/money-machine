"""Earn the Session 14 deployment-target key.

The proof calls the selector. A paragraph that says the host is deployed does
not earn the key. The closure key stays false.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

from money_machine.deploy.target import (
    DeploymentTargetRefusal,
    PaidHostAuthority,
    select_deployment_target,
)

TARGET_EVIDENCE_KEY = "deployment_target_recorded"
_CLOSURE_EVIDENCE_KEY = "evidence_closure_commit_recorded"
EARNED_EVIDENCE_KEYS = frozenset({TARGET_EVIDENCE_KEY})
_SESSION_14_KEYS = frozenset(
    {
        TARGET_EVIDENCE_KEY,
        "production_packaging_defined",
        "release_rollback_implemented",
        "service_controls_fail_closed",
        "control_files_and_checkpoint_current",
        _CLOSURE_EVIDENCE_KEY,
    }
)
_CONTROL_FILES = (
    Path("docs/control/IMPLEMENTATION_STATE.json"),
    Path("docs/control/IMPLEMENTATION_LOG.md"),
    Path("docs/control/DECISIONS.md"),
    Path("docs/control/TEST_EVIDENCE.md"),
    Path("docs/control/NEXT_SESSION.md"),
    Path("docs/control/SESSION_EVIDENCE.md"),
)
_CLOSURE_HEAD = "fbaf8e8bdd73b1e3b6fa4f87158574057b72d18a"
_SESSION_14_PROMPT = "17_SESSION_14_DEPLOYMENT.md"
_POINTER_REVISION = 106
_UPDATED_AT = "2026-10-17T15:00:00Z"
_TARGET_IS_TRUE = True


class Session14ProofError(ValueError):
    """The Session 14 selector did not earn its evidence key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def prove_session_14() -> frozenset[str]:
    """Return the earned Session 14 keys. A miss raises instead of returning them."""
    _prove_target()
    _prove_control_files()
    return EARNED_EVIDENCE_KEYS


def _prove_target() -> None:
    module = Path(__file__).resolve().parents[1] / "deploy" / "target.py"
    _refuse_network(module)
    selected = select_deployment_target()
    if (
        selected.target != "local-wsl"
        or selected.host_created is not False
        or "local and single-server" not in selected.rationale
        or "Exit 78" not in selected.rationale
        or "No unapproved spend" not in selected.rationale
        or "No host is created" not in selected.rationale
    ):
        raise Session14ProofError("local_wsl")
    _require_refusal("new-paid", None, "unapproved_spend", "new_paid")
    _require_refusal("", None, "empty_target", "empty_target")
    _require_refusal("kubernetes", None, "unknown_target", "unknown_target")
    _require_refusal(
        "new-paid",
        PaidHostAuthority(record_id="recorded-authority", approved_paid_host=False),
        "unapproved_spend",
        "new_paid",
    )
    named = select_deployment_target(
        requested="new-paid",
        authority=PaidHostAuthority(record_id="recorded-authority", approved_paid_host=True),
    )
    if named.target != "new-paid" or named.host_created is not False:
        raise Session14ProofError("host_created")


def _require_refusal(
    requested: str,
    authority: PaidHostAuthority | None,
    code: str,
    proof_code: str,
) -> None:
    try:
        select_deployment_target(requested=requested, authority=authority)
    except DeploymentTargetRefusal as error:
        if error.code != code:
            raise Session14ProofError(proof_code) from error
    else:
        raise Session14ProofError(proof_code)


def _refuse_network(module: Path) -> None:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imported.append(node.module)
    folded = " ".join(imported)
    banned = ("socket", "httpx", "urllib", "requests", "dotenv", "subprocess")
    if any(token in folded for token in banned):
        raise Session14ProofError("target_socket")


def _prove_control_files() -> None:
    """The continuity files and the catalogue match the checked-in pointer."""
    root = Path(__file__).resolve().parents[3]
    for relative in _CONTROL_FILES:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise Session14ProofError("control_files")
    # Imported here because session_evidence imports state, and state imports this proof.
    from money_machine.control.session_evidence import render_session_evidence

    catalogue = root / "docs/control/SESSION_EVIDENCE.md"
    if catalogue.read_text(encoding="utf-8") != render_session_evidence():
        raise Session14ProofError("control_checkpoint")
    decoded: object = json.loads(
        (root / "docs/control/IMPLEMENTATION_STATE.json").read_text(encoding="utf-8")
    )
    if not isinstance(decoded, dict):
        raise Session14ProofError("control_checkpoint")
    evidence = decoded.get("required_completion_evidence")
    recorded = set(evidence) if isinstance(evidence, dict) else set()
    values_are_bool = isinstance(evidence, dict) and all(
        isinstance(value, bool) for value in evidence.values()
    )
    target_matches = isinstance(evidence, dict) and _target_matches(evidence)
    if (
        decoded.get("current_session") != 14
        or decoded.get("session_status") != "incomplete"
        or decoded.get("state_revision") != _POINTER_REVISION
        or decoded.get("updated_at") != _UPDATED_AT
        or decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or decoded.get("head_sha") != _CLOSURE_HEAD
        or recorded != set(_SESSION_14_KEYS)
        or not values_are_bool
        or not isinstance(evidence, dict)
        or len(evidence) != len(recorded)
        or decoded.get("next_session") != 14
        or decoded.get("completed_sessions") != list(range(14))
        or decoded.get("next_prompt") != _SESSION_14_PROMPT
        or not target_matches
    ):
        raise Session14ProofError("control_checkpoint")


def _target_matches(evidence: dict[str, object]) -> bool:
    target = evidence.get(TARGET_EVIDENCE_KEY)
    others = [value for key, value in evidence.items() if key != TARGET_EVIDENCE_KEY]
    if _TARGET_IS_TRUE:
        return target is True and all(value is False for value in others)
    return target is False and all(value is False for value in others)
