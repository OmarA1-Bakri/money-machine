"""The Session 14 target key flips only through the proof-gated transition."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import cast

import pytest

from money_machine.control.session_14_proof import EARNED_EVIDENCE_KEYS, prove_session_14
from money_machine.control.state import (
    SESSION_EVIDENCE_KEYS,
    ControlState,
    ControlStateError,
    validate_session_14_evidence_record,
)
from money_machine.deploy.target import (
    DeploymentTargetRefusal,
    PaidHostAuthority,
    select_deployment_target,
)

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
EARNED_AT = "2026-10-17T15:00:00Z"


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _previous() -> ControlState:
    """Revision 105, rebuilt after the target record replaces the live file."""
    state = _live()
    state["state_revision"] = 105
    state["current_session"] = 14
    state["session_status"] = "incomplete"
    state["updated_at"] = "2026-10-17T14:55:00Z"
    state["required_completion_evidence"] = dict.fromkeys(sorted(SESSION_EVIDENCE_KEYS[14]), False)
    return state


def _earned(previous: ControlState) -> ControlState:
    current = copy.deepcopy(previous)
    current["state_revision"] = previous["state_revision"] + 1
    current["updated_at"] = EARNED_AT
    evidence = dict(current["required_completion_evidence"])
    for key in EARNED_EVIDENCE_KEYS:
        evidence[key] = True
    current["required_completion_evidence"] = evidence
    return current


def test_selector_returns_the_local_host() -> None:
    selected = select_deployment_target()
    assert selected.target == "local-wsl"
    assert selected.host_created is False
    assert "local and single-server" in selected.rationale
    assert "Exit 78" in selected.rationale
    assert "No unapproved spend" in selected.rationale
    assert "No host is created" in selected.rationale


def test_selector_refuses_a_new_paid_host() -> None:
    with pytest.raises(DeploymentTargetRefusal, match="unapproved_spend"):
        select_deployment_target(requested="new-paid")
    with pytest.raises(DeploymentTargetRefusal, match="unapproved_spend"):
        select_deployment_target(
            requested="new-paid",
            authority=PaidHostAuthority(record_id="recorded-authority", approved_paid_host=False),
        )


def test_selector_refuses_an_empty_or_unknown_target() -> None:
    with pytest.raises(DeploymentTargetRefusal, match="empty_target"):
        select_deployment_target(requested="")
    with pytest.raises(DeploymentTargetRefusal, match="unknown_target"):
        select_deployment_target(requested="kubernetes")


def test_named_paid_host_still_creates_nothing() -> None:
    named = select_deployment_target(
        requested="new-paid",
        authority=PaidHostAuthority(record_id="recorded-authority", approved_paid_host=True),
    )
    assert named.target == "new-paid"
    assert named.host_created is False


def test_proof_earns_the_recorded_key() -> None:
    assert prove_session_14() == EARNED_EVIDENCE_KEYS


def test_record_accepts_the_target_key_and_refuses_the_closure_key() -> None:
    previous = _previous()
    validate_session_14_evidence_record(previous, _earned(previous))
    closure = _earned(previous)
    evidence = dict(closure["required_completion_evidence"])
    evidence["evidence_closure_commit_recorded"] = True
    closure["required_completion_evidence"] = evidence
    with pytest.raises(ControlStateError, match="closure key stays false"):
        validate_session_14_evidence_record(previous, closure)


def test_record_refuses_a_second_key() -> None:
    previous = _previous()
    current = _earned(previous)
    evidence = dict(current["required_completion_evidence"])
    evidence["control_files_and_checkpoint_current"] = True
    current["required_completion_evidence"] = evidence
    with pytest.raises(ControlStateError, match="exactly the keys"):
        validate_session_14_evidence_record(previous, current)
