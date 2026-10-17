"""The deployed-state key flips only through the proof-gated transition."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import cast

import pytest

from money_machine.control.session_15_proof import EARNED_EVIDENCE_KEYS, prove_session_15
from money_machine.control.state import (
    SESSION_EVIDENCE_KEYS,
    ControlState,
    ControlStateError,
    validate_session_15_evidence_record,
)
from money_machine.deploy.deployed_state import DeployedStateRefusal, check_deployed_state

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
RECORDED_AT = "2026-10-17T16:10:00Z"
CLOSURE_HEAD = "02c26f39ac8800db03ae7f5d1d346487a5ce123e"
PREVIOUS_REVISION = 112
PREVIOUS_AT = "2026-10-17T16:00:00Z"


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _previous() -> ControlState:
    """Revision 112, the activated pointer before this record."""
    state = _live()
    state["state_revision"] = PREVIOUS_REVISION
    state["current_session"] = 15
    state["session_status"] = "incomplete"
    state["updated_at"] = PREVIOUS_AT
    state["completed_sessions"] = list(range(15))
    state["next_session"] = 15
    state["head_sha"] = CLOSURE_HEAD
    state["evidence_closure_commit_sha"] = CLOSURE_HEAD
    state["required_completion_evidence"] = dict.fromkeys(SESSION_EVIDENCE_KEYS[15], False)
    return state


def _earned(previous: ControlState) -> ControlState:
    current = copy.deepcopy(previous)
    current["state_revision"] = previous["state_revision"] + 1
    current["updated_at"] = RECORDED_AT
    evidence = dict(current["required_completion_evidence"])
    for key in EARNED_EVIDENCE_KEYS:
        evidence[key] = True
    current["required_completion_evidence"] = evidence
    return current


def test_the_checkpoint_refuses_a_live_smoke() -> None:
    checked = check_deployed_state(
        ROOT,
        expected_revision=115,
        expected_updated_at="2026-10-17T16:20:00Z",
        expected_true_keys=frozenset(
            {
                "deployed_state_checked",
                "provider_connections_fail_closed",
                "standing_authority_recorded",
            }
        ),
        closure_head=CLOSURE_HEAD,
    )
    assert checked.revision == 115
    assert checked.smoke_ran is False
    assert checked.services_started is False
    assert checked.exit_78_held is True
    assert checked.true_keys == (
        "deployed_state_checked",
        "provider_connections_fail_closed",
        "standing_authority_recorded",
    )


def test_a_live_smoke_is_refused() -> None:
    with pytest.raises(DeployedStateRefusal, match="live_smoke"):
        check_deployed_state(
            ROOT,
            expected_revision=PREVIOUS_REVISION,
            expected_updated_at=PREVIOUS_AT,
            expected_true_keys=frozenset(),
            closure_head=CLOSURE_HEAD,
            live_smoke=True,
        )


def test_a_docker_socket_is_refused() -> None:
    with pytest.raises(DeployedStateRefusal, match="docker_socket"):
        check_deployed_state(
            ROOT,
            expected_revision=PREVIOUS_REVISION,
            expected_updated_at=PREVIOUS_AT,
            expected_true_keys=frozenset(),
            closure_head=CLOSURE_HEAD,
            docker_socket=True,
        )


def test_starting_services_is_refused() -> None:
    with pytest.raises(DeployedStateRefusal, match="service_start"):
        check_deployed_state(
            ROOT,
            expected_revision=PREVIOUS_REVISION,
            expected_updated_at=PREVIOUS_AT,
            expected_true_keys=frozenset(),
            closure_head=CLOSURE_HEAD,
            start_services=True,
        )


def test_proof_earns_the_deployed_state_key() -> None:
    assert prove_session_15() == EARNED_EVIDENCE_KEYS
    assert "deployed_state_checked" in EARNED_EVIDENCE_KEYS


def test_record_accepts_the_deployed_state_and_refuses_the_closure_key() -> None:
    previous = _previous()
    validate_session_15_evidence_record(previous, _earned(previous))
    closure = _earned(previous)
    evidence = dict(closure["required_completion_evidence"])
    evidence["evidence_closure_commit_recorded"] = True
    closure["required_completion_evidence"] = evidence
    with pytest.raises(ControlStateError, match="closure key stays false"):
        validate_session_15_evidence_record(previous, closure)


def test_record_refuses_an_unchanged_key_set() -> None:
    previous = _previous()
    current = copy.deepcopy(previous)
    current["state_revision"] = previous["state_revision"] + 1
    current["updated_at"] = RECORDED_AT
    with pytest.raises(ControlStateError, match="at least one key"):
        validate_session_15_evidence_record(previous, current)
