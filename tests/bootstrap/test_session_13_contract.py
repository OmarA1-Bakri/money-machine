"""Session 13 is activated. Every Session 13 key is false."""

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
SESSION_13_KEYS = frozenset(
    {
        "implementation_matrix_recorded",
        "synthetic_paths_implemented",
        "failure_injection_implemented",
        "backup_restore_fixture_implemented",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
ACTIVATED_AT = "2026-10-17T13:45:00Z"
CLOSURE_HEAD = "02c26f39ac8800db03ae7f5d1d346487a5ce123e"


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _activation_candidate(evidence: dict[str, bool]) -> tuple[ControlState, ControlState]:
    """The revision-97 close, rebuilt after activation replaces the live file."""
    previous = _live()
    previous["state_revision"] = 97
    previous["session_status"] = "complete"
    previous["current_session"] = 12
    previous["completed_sessions"] = list(range(13))
    previous["next_session"] = 13
    previous["next_prompt"] = SESSION_PROMPTS[13]
    previous["updated_at"] = "2026-10-17T13:35:00Z"
    previous["required_completion_evidence"] = {key: True for key in SESSION_EVIDENCE_KEYS[12]}
    current = copy.deepcopy(previous)
    current["state_revision"] = 98
    current["session_status"] = "incomplete"
    current["current_session"] = 13
    current["updated_at"] = ACTIVATED_AT
    current["required_completion_evidence"] = evidence
    return previous, current


def test_session_13_contract_is_the_fixture_surface() -> None:
    """Live injection, a live backup, Exit 78, and the exit string are not keys."""
    assert SESSION_EVIDENCE_KEYS[13] == SESSION_13_KEYS
    assert "SESSION_13_E2E_AND_HARDENING_COMPLETE" not in SESSION_EVIDENCE_KEYS[13]


def test_live_pointer_is_incomplete_session_13() -> None:
    """Session 13 stays closed. Session 15 is activated and every key is false."""
    live = _live()
    text = STATE_PATH.read_text(encoding="utf-8")
    assert live["state_revision"] == 112
    assert live["current_session"] == 15
    assert live["session_status"] == "incomplete"
    assert live["updated_at"] == "2026-10-17T16:00:00Z"
    assert live["completed_sessions"] == list(range(15))
    assert live["next_session"] == 15
    assert live["next_prompt"] == SESSION_PROMPTS[15]
    assert live["head_sha"] == CLOSURE_HEAD
    assert live["evidence_closure_commit_sha"] == CLOSURE_HEAD
    evidence = live["required_completion_evidence"]
    assert set(evidence) == set(SESSION_EVIDENCE_KEYS[15])
    assert not any(evidence.values())
    assert "SESSION_13_E2E_AND_HARDENING_COMPLETE" not in text


def test_session_13_activation_shape_is_accepted() -> None:
    """The revision-97 close still validates. This test does not write the state file."""
    before = STATE_PATH.read_bytes()
    previous, current = _activation_candidate(dict.fromkeys(SESSION_13_KEYS, False))

    validate_activation_transition(previous, current)

    assert STATE_PATH.read_bytes() == before
    assert previous["state_revision"] == 97
    assert previous["current_session"] == 12
    assert current["state_revision"] == 98
    assert current["current_session"] == 13
    assert current["session_status"] == "incomplete"
    assert not any(current["required_completion_evidence"].values())


def test_session_13_activation_rejects_one_true_key() -> None:
    evidence = dict.fromkeys(SESSION_13_KEYS, False)
    evidence["implementation_matrix_recorded"] = True
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="activation cannot claim any completion evidence"):
        validate_activation_transition(previous, current)


def test_session_13_activation_rejects_a_missing_key() -> None:
    evidence = dict.fromkeys(SESSION_13_KEYS, False)
    del evidence["failure_injection_implemented"]
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="exactly the session 13 completion"):
        validate_activation_transition(previous, current)


def test_session_13_activation_rejects_an_extra_key() -> None:
    evidence = dict.fromkeys(SESSION_13_KEYS, False)
    evidence["live_backup"] = False
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="exactly the session 13 completion"):
        validate_activation_transition(previous, current)
