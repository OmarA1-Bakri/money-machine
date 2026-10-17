"""Session 15 contract is installed. The session is not activated."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import cast

import pytest

from money_machine.control.state import (
    SESSION_EVIDENCE_KEYS,
    ControlState,
    ControlStateError,
    validate_activation_transition,
)

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
SESSION_15_KEYS = frozenset(
    {
        "deployed_state_checked",
        "provider_connections_fail_closed",
        "standing_authority_recorded",
        "linked_workflow_fixture",
        "acceptance_matrix_recorded",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
ACTIVATED_AT = "2026-10-17T16:00:00Z"
CLOSURE_HEAD = "02c26f39ac8800db03ae7f5d1d346487a5ce123e"


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _activation_candidate(evidence: dict[str, bool]) -> tuple[ControlState, ControlState]:
    """The revision-111 close, rebuilt after activation replaces the live file."""
    previous = _live()
    previous["state_revision"] = 111
    previous["session_status"] = "complete"
    previous["current_session"] = 14
    previous["completed_sessions"] = list(range(15))
    previous["next_session"] = 15
    previous["next_prompt"] = "18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md"
    previous["updated_at"] = "2026-10-17T15:35:00Z"
    previous["head_sha"] = CLOSURE_HEAD
    previous["evidence_closure_commit_sha"] = CLOSURE_HEAD
    previous["required_completion_evidence"] = {key: True for key in SESSION_EVIDENCE_KEYS[14]}
    current = copy.deepcopy(previous)
    current["state_revision"] = 112
    current["session_status"] = "incomplete"
    current["current_session"] = 15
    current["updated_at"] = ACTIVATED_AT
    current["required_completion_evidence"] = evidence
    return previous, current


def test_session_15_contract_is_the_fixture_surface() -> None:
    """A live account, a publish, a purchase, and the exit string are not keys."""
    assert SESSION_EVIDENCE_KEYS[15] == SESSION_15_KEYS
    assert "HANDS_OFF_MONEY_MACHINE_COMMISSIONED" not in SESSION_EVIDENCE_KEYS[15]
    assert "v1.0.0" not in SESSION_EVIDENCE_KEYS[15]


def test_live_pointer_stays_complete_session_14() -> None:
    """Session 14 stays closed. Session 15 is activated and every key is false."""
    live = _live()
    text = STATE_PATH.read_text(encoding="utf-8")
    assert live["state_revision"] == 113
    assert live["current_session"] == 15
    assert live["session_status"] == "incomplete"
    assert live["updated_at"] == "2026-10-17T16:10:00Z"
    assert live["completed_sessions"] == list(range(15))
    assert live["next_session"] == 15
    assert live["head_sha"] == CLOSURE_HEAD
    evidence = live["required_completion_evidence"]
    assert set(evidence) == set(SESSION_15_KEYS)
    assert evidence["deployed_state_checked"] is True
    assert sum(1 for value in evidence.values() if value) == 1
    assert "HANDS_OFF_MONEY_MACHINE_COMMISSIONED" not in text


def test_session_15_activation_shape_is_accepted() -> None:
    """The revision-111 close can install every Session 15 key false. It does not write."""
    before = STATE_PATH.read_bytes()
    previous, current = _activation_candidate(dict.fromkeys(SESSION_15_KEYS, False))

    validate_activation_transition(previous, current)

    assert STATE_PATH.read_bytes() == before
    assert previous["state_revision"] == 111
    assert previous["current_session"] == 14
    assert previous["session_status"] == "complete"
    assert current["state_revision"] == 112
    assert current["current_session"] == 15
    assert current["session_status"] == "incomplete"
    assert current["next_session"] == 15
    assert not any(current["required_completion_evidence"].values())


def test_session_15_activation_rejects_one_true_key() -> None:
    evidence = dict.fromkeys(SESSION_15_KEYS, False)
    evidence["deployed_state_checked"] = True
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="activation cannot claim any completion evidence"):
        validate_activation_transition(previous, current)


def test_session_15_activation_rejects_a_missing_key() -> None:
    evidence = dict.fromkeys(SESSION_15_KEYS, False)
    del evidence["linked_workflow_fixture"]
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="exactly the session 15 completion"):
        validate_activation_transition(previous, current)


def test_session_15_activation_rejects_an_extra_key() -> None:
    evidence = dict.fromkeys(SESSION_15_KEYS, False)
    evidence["live_account"] = False
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="exactly the session 15 completion"):
        validate_activation_transition(previous, current)
