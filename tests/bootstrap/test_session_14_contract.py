"""Session 14 contract is installed. The deployment target is recorded."""

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
SESSION_14_KEYS = frozenset(
    {
        "deployment_target_recorded",
        "production_packaging_defined",
        "release_rollback_implemented",
        "service_controls_fail_closed",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
ACTIVATED_AT = "2026-10-17T14:55:00Z"
CLOSURE_HEAD = "fbaf8e8bdd73b1e3b6fa4f87158574057b72d18a"


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _activation_candidate(evidence: dict[str, bool]) -> tuple[ControlState, ControlState]:
    """The revision-104 close, rebuilt after activation replaces the live file."""
    previous = _live()
    previous["state_revision"] = 104
    previous["session_status"] = "complete"
    previous["current_session"] = 13
    previous["completed_sessions"] = list(range(14))
    previous["next_session"] = 14
    previous["next_prompt"] = SESSION_PROMPTS[14]
    previous["updated_at"] = "2026-10-17T14:40:00Z"
    previous["head_sha"] = CLOSURE_HEAD
    previous["evidence_closure_commit_sha"] = CLOSURE_HEAD
    previous["required_completion_evidence"] = {key: True for key in SESSION_EVIDENCE_KEYS[13]}
    current = copy.deepcopy(previous)
    current["state_revision"] = 105
    current["session_status"] = "incomplete"
    current["current_session"] = 14
    current["updated_at"] = ACTIVATED_AT
    current["required_completion_evidence"] = evidence
    return previous, current


def test_session_14_contract_is_the_fixture_surface() -> None:
    """A live deploy, a paid host, Exit 78, and the exit string are not keys."""
    assert SESSION_EVIDENCE_KEYS[14] == SESSION_14_KEYS
    assert "SESSION_14_PRODUCTION_DEPLOYMENT_COMPLETE" not in SESSION_EVIDENCE_KEYS[14]
    assert "v0.1.0-rc1" not in SESSION_EVIDENCE_KEYS[14]


def test_live_pointer_is_incomplete_session_14() -> None:
    """Session 14 is complete. Session 15 is not activated."""
    live = _live()
    text = STATE_PATH.read_text(encoding="utf-8")
    assert live["state_revision"] == 111
    assert live["current_session"] == 14
    assert live["session_status"] == "complete"
    assert live["updated_at"] == "2026-10-17T15:35:00Z"
    assert live["next_session"] == 15
    assert live["next_prompt"] == SESSION_PROMPTS[15]
    assert live["head_sha"] == "02c26f39ac8800db03ae7f5d1d346487a5ce123e"
    evidence = live["required_completion_evidence"]
    assert set(evidence) == set(SESSION_14_KEYS)
    assert evidence["deployment_target_recorded"] is True
    assert evidence["production_packaging_defined"] is True
    assert evidence["release_rollback_implemented"] is True
    assert evidence["service_controls_fail_closed"] is True
    assert evidence["control_files_and_checkpoint_current"] is True
    assert evidence["evidence_closure_commit_recorded"] is True
    assert sum(1 for value in evidence.values() if value is True) == 6
    assert "SESSION_14_PRODUCTION_DEPLOYMENT_COMPLETE" not in text


def test_session_14_activation_shape_is_accepted() -> None:
    """A candidate from the revision-104 close installs every key false."""
    before = STATE_PATH.read_bytes()
    previous, current = _activation_candidate(dict.fromkeys(SESSION_14_KEYS, False))

    validate_activation_transition(previous, current)

    assert STATE_PATH.read_bytes() == before
    assert previous["state_revision"] == 104
    assert previous["current_session"] == 13
    assert current["state_revision"] == 105
    assert current["current_session"] == 14
    assert current["session_status"] == "incomplete"
    assert current["next_session"] == 14
    assert not any(current["required_completion_evidence"].values())


def test_session_14_activation_rejects_one_true_key() -> None:
    evidence = dict.fromkeys(SESSION_14_KEYS, False)
    evidence["deployment_target_recorded"] = True
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="activation cannot claim any completion evidence"):
        validate_activation_transition(previous, current)


def test_session_14_activation_rejects_a_missing_key() -> None:
    evidence = dict.fromkeys(SESSION_14_KEYS, False)
    del evidence["release_rollback_implemented"]
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="exactly the session 14 completion"):
        validate_activation_transition(previous, current)


def test_session_14_activation_rejects_an_extra_key() -> None:
    evidence = dict.fromkeys(SESSION_14_KEYS, False)
    evidence["live_deploy"] = False
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="exactly the session 14 completion"):
        validate_activation_transition(previous, current)
