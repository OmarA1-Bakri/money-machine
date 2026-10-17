"""Session 11's evidence contract is installed. Activation is not applied."""

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
SESSION_11_KEYS = frozenset(
    {
        "support_intake_implemented",
        "incident_routing_implemented",
        "repair_resolution_implemented",
        "draft_reply_implemented",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
ACTIVATED_AT = "2026-10-17T12:05:00Z"


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _session_10_close() -> ControlState:
    """The revision-83 close, rebuilt after activation replaces the live file."""
    previous = _live()
    previous["state_revision"] = 83
    previous["session_status"] = "complete"
    previous["current_session"] = 10
    previous["completed_sessions"] = list(range(11))
    previous["next_session"] = 11
    previous["next_prompt"] = SESSION_PROMPTS[11]
    previous["updated_at"] = "2026-10-17T12:00:00Z"
    previous["required_completion_evidence"] = {key: True for key in SESSION_EVIDENCE_KEYS[10]}
    contract = dict(previous["transition_contract"])
    contract["completion_requires_next_session"] = 11
    previous["transition_contract"] = contract
    return previous


def _activation_candidate(evidence: dict[str, bool]) -> tuple[ControlState, ControlState]:
    previous = _session_10_close()
    current = copy.deepcopy(previous)
    current["state_revision"] = previous["state_revision"] + 1
    current["session_status"] = "incomplete"
    current["current_session"] = 11
    current["updated_at"] = ACTIVATED_AT
    current["required_completion_evidence"] = evidence
    return previous, current


def test_session_11_contract_is_the_fixture_surface() -> None:
    """Live send, commissioning, Exit 78, and the exit string are not keys."""
    assert SESSION_EVIDENCE_KEYS[11] == SESSION_11_KEYS
    assert "SESSION_11_SUPPORT_AND_REPAIR_COMPLETE" not in SESSION_EVIDENCE_KEYS[11]


def test_live_pointer_is_the_session_11_activation() -> None:
    """Session 11 stays closed. Session 14 is complete."""
    live = _live()
    text = STATE_PATH.read_text(encoding="utf-8")
    expected = dict.fromkeys(sorted(SESSION_EVIDENCE_KEYS[15]), False)
    expected["deployed_state_checked"] = True
    expected["provider_connections_fail_closed"] = True
    assert live["state_revision"] == 114
    assert live["current_session"] == 15
    assert live["session_status"] == "incomplete"
    assert live["completed_sessions"] == list(range(15))
    assert live["next_session"] == 15
    assert live["next_prompt"] == "18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md"
    assert live["head_sha"] == "02c26f39ac8800db03ae7f5d1d346487a5ce123e"
    assert live["required_completion_evidence"] == expected
    assert "SESSION_11_SUPPORT_AND_REPAIR_COMPLETE" not in text


def test_session_11_activation_shape_is_accepted() -> None:
    """The revision-83 close still validates. This test does not write the state file."""
    before = STATE_PATH.read_bytes()
    previous, current = _activation_candidate(dict.fromkeys(SESSION_11_KEYS, False))

    validate_activation_transition(previous, current)

    assert STATE_PATH.read_bytes() == before
    assert previous["state_revision"] == 83
    assert previous["current_session"] == 10
    assert current["state_revision"] == 84
    assert current["current_session"] == 11
    assert current["session_status"] == "incomplete"
    assert not any(current["required_completion_evidence"].values())


def test_session_11_activation_rejects_one_true_key() -> None:
    evidence = dict.fromkeys(SESSION_11_KEYS, False)
    evidence["support_intake_implemented"] = True
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="activation cannot claim any completion evidence"):
        validate_activation_transition(previous, current)


def test_session_11_activation_rejects_a_missing_key() -> None:
    evidence = dict.fromkeys(SESSION_11_KEYS, False)
    del evidence["draft_reply_implemented"]
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="exactly the session 11 completion"):
        validate_activation_transition(previous, current)


def test_session_11_activation_rejects_an_extra_key() -> None:
    evidence = dict.fromkeys(SESSION_11_KEYS, False)
    evidence["live_send"] = False
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="exactly the session 11 completion"):
        validate_activation_transition(previous, current)
