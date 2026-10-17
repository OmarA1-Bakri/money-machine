"""Session 09's evidence contract is installed and the session is complete."""

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
SESSION_09_KEYS = frozenset(
    {
        "etsy_preflight_implemented",
        "publishing_ramp_implemented",
        "mutation_receipt_implemented",
        "fixture_draft_package_implemented",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
ACTIVATED_AT = "2026-10-17T10:40:00Z"


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _session_08_close() -> ControlState:
    """The revision-69 close, rebuilt after later transitions replaced the live file."""
    previous = _live()
    previous["state_revision"] = 69
    previous["session_status"] = "complete"
    previous["current_session"] = 8
    previous["completed_sessions"] = list(range(9))
    previous["next_session"] = 9
    previous["next_prompt"] = SESSION_PROMPTS[9]
    previous["updated_at"] = "2026-10-17T09:49:00Z"
    previous["required_completion_evidence"] = {key: True for key in SESSION_EVIDENCE_KEYS[8]}
    contract = dict(previous["transition_contract"])
    contract["completion_requires_next_session"] = 9
    previous["transition_contract"] = contract
    return previous


def _activation_candidate(evidence: dict[str, bool]) -> tuple[ControlState, ControlState]:
    previous = _session_08_close()
    current = copy.deepcopy(previous)
    current["state_revision"] = previous["state_revision"] + 1
    current["session_status"] = "incomplete"
    current["current_session"] = 9
    current["updated_at"] = ACTIVATED_AT
    current["required_completion_evidence"] = evidence
    return previous, current


def test_session_09_contract_is_the_fixture_surface() -> None:
    """Live publish, commissioning, and the exit string are not keys."""
    assert SESSION_EVIDENCE_KEYS[9] == SESSION_09_KEYS
    assert "SESSION_09_ETSY_PUBLISHING_COMPLETE" not in SESSION_EVIDENCE_KEYS[9]


def test_live_pointer_is_incomplete_session_10() -> None:
    """Session 09 stays closed. Session 10 records the metrics fixture and the maturity clock."""
    live = _live()
    text = STATE_PATH.read_text(encoding="utf-8")
    assert live["state_revision"] == 79
    assert live["current_session"] == 10
    assert live["session_status"] == "incomplete"
    assert live["completed_sessions"] == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert live["next_session"] == 10
    assert live["next_prompt"] == SESSION_PROMPTS[10]
    assert live["head_sha"] == "cfb36462994ecba833f31ba869f2aba627f6060d"
    evidence = live["required_completion_evidence"]
    assert evidence["metrics_fixture_implemented"] is True
    assert evidence["maturity_clock_implemented"] is True
    assert sum(1 for value in evidence.values() if value) == 2
    assert "SESSION_09_ETSY_PUBLISHING_COMPLETE" not in text


def test_session_09_activation_shape_is_accepted() -> None:
    """The revision-69 close still validates. This test does not write the state file."""
    before = STATE_PATH.read_bytes()
    previous, current = _activation_candidate(dict.fromkeys(SESSION_09_KEYS, False))

    validate_activation_transition(previous, current)

    assert STATE_PATH.read_bytes() == before
    assert previous["state_revision"] == 69
    assert previous["current_session"] == 8
    assert previous["session_status"] == "complete"


def test_session_09_activation_rejects_one_true_key() -> None:
    evidence = dict.fromkeys(SESSION_09_KEYS, False)
    evidence["etsy_preflight_implemented"] = True
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="activation cannot claim any completion evidence"):
        validate_activation_transition(previous, current)


def test_session_09_activation_rejects_a_missing_key() -> None:
    evidence = dict.fromkeys(SESSION_09_KEYS, False)
    del evidence["fixture_draft_package_implemented"]
    previous, current = _activation_candidate(evidence)

    with pytest.raises(ControlStateError, match="exactly the session 09 completion"):
        validate_activation_transition(previous, current)
