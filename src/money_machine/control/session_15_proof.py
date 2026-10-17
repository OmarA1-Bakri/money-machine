"""Earn the Session 15 deployed-state key.

The proof calls the deployed-state check. A paragraph that says the smoke
passed does not earn a key. The closure key stays false.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

from money_machine.deploy.checkpoint import CheckpointRefusal
from money_machine.deploy.deployed_state import DeployedStateRefusal, check_deployed_state

DEPLOYED_STATE_KEY = "deployed_state_checked"
EARNED_EVIDENCE_KEYS = frozenset({DEPLOYED_STATE_KEY})
_CLOSURE_HEAD = "02c26f39ac8800db03ae7f5d1d346487a5ce123e"
_POINTER_REVISION = 113
_UPDATED_AT = "2026-10-17T16:10:00Z"
_TRUE_KEYS: frozenset[str] = frozenset({DEPLOYED_STATE_KEY})
_MODULE = Path(__file__).resolve().parents[1] / "deploy" / "deployed_state.py"
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
