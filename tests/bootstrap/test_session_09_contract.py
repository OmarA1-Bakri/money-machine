"""Session 09's evidence contract is installed. Activation is not applied."""

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


def _activation_candidate(evidence: dict[str, bool]) -> tuple[ControlState, ControlState]:
    previous = _live()
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


def test_session_09_activation_shape_is_accepted_and_the_live_file_stays() -> None:
    """The revision-69 close can install the six keys all false. This test does not write it."""
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
