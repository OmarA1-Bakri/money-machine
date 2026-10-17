"""Session 10's evidence contract is installed. Activation is not applied."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import cast

import pytest

from money_machine.control.state import (
    SESSION_EVIDENCE_KEYS,
    SESSION_PROMPTS,
    ControlState,
    ControlStateError,
    validate_activation_transition,
)

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
SESSION_10_KEYS = frozenset(
    {
        "metrics_fixture_implemented",
        "maturity_clock_implemented",
        "portfolio_eligibility_implemented",
        "closed_loop_store_implemented",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
ACTIVATED_AT = "2026-10-17T11:25:00Z"


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _session_09_close() -> ControlState:
    """The revision-76 close, rebuilt after a later activation replaces the live file."""
    previous = _live()
    previous["state_revision"] = 76
    previous["session_status"] = "complete"
    previous["current_session"] = 9
    previous["completed_sessions"] = list(range(10))
    previous["next_session"] = 10
    previous["next_prompt"] = SESSION_PROMPTS[10]
    previous["updated_at"] = "2026-10-17T11:20:00Z"
    previous["required_completion_evidence"] = {key: True for key in SESSION_EVIDENCE_KEYS[9]}
    contract = dict(previous["transition_contract"])
    contract["completion_requires_next_session"] = 10
    previous["transition_contract"] = contract
    return previous


def _activation_candidate(evidence: dict[str, bool]) -> tuple[ControlState, ControlState]:
    previous = _session_09_close()
    current = copy.deepcopy(previous)
    current["state_revision"] = previous["state_revision"] + 1
    current["session_status"] = "incomplete"
    current["current_session"] = 10
    current["updated_at"] = ACTIVATED_AT
    current["required_completion_evidence"] = evidence
    return previous, current


def test_session_10_contract_is_the_fixture_surface() -> None:
    """Live stats, deactivation, commissioning, and the exit string are not keys."""
    assert SESSION_EVIDENCE_KEYS[10] == SESSION_10_KEYS
    assert "SESSION_10_CLOSED_LOOP_AUTOMATION_COMPLETE" not in SESSION_EVIDENCE_KEYS[10]


def test_live_pointer_records_the_closure_key() -> None:
    """Session 10 stays closed. Session 14 records the release plan."""
    live = _live()
    text = STATE_PATH.read_text(encoding="utf-8")
    evidence = dict.fromkeys(sorted(SESSION_EVIDENCE_KEYS[14]), False)
    evidence["deployment_target_recorded"] = True
    evidence["production_packaging_defined"] = True
    evidence["release_rollback_implemented"] = True
    evidence["service_controls_fail_closed"] = True
    evidence["control_files_and_checkpoint_current"] = True
    assert live["state_revision"] == 110
    assert live["current_session"] == 14
    assert live["session_status"] == "incomplete"
    assert live["completed_sessions"] == list(range(14))
    assert live["next_session"] == 14
    assert live["next_prompt"] == SESSION_PROMPTS[14]
    assert live["head_sha"] == "fbaf8e8bdd73b1e3b6fa4f87158574057b72d18a"
    assert live["required_completion_evidence"] == evidence
    assert "SESSION_10_CLOSED_LOOP_AUTOMATION_COMPLETE" not in text


def test_session_10_activation_shape_is_accepted() -> None:
    """The revision-76 close still validates. This test does not write the state file."""
    before = STATE_PATH.read_bytes()
    previous, current = _activation_candidate(dict.fromkeys(SESSION_10_KEYS, False))

    validate_activation_transition(previous, current)

    assert STATE_PATH.read_bytes() == before
    assert previous["state_revision"] == 76
    assert previous["current_session"] == 9
    assert current["current_session"] == 10
    assert current["session_status"] == "incomplete"
    assert not any(current["required_completion_evidence"].values())


def test_session_10_activation_rejects_one_true_key() -> None:
    evidence = dict.fromkeys(SESSION_10_KEYS, False)
    evidence["metrics_fixture_implemented"] = True
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="activation cannot claim any completion evidence"):
        validate_activation_transition(previous, current)


def test_session_10_activation_rejects_a_missing_key() -> None:
    evidence = dict.fromkeys(SESSION_10_KEYS, False)
    del evidence["closed_loop_store_implemented"]
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="exactly the session 10 completion"):
        validate_activation_transition(previous, current)
