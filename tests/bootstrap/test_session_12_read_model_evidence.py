"""The Session 12 read-model key flips only through the proof-gated transition."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import cast

import pytest

from money_machine.control.session_12_proof import (
    ACTIONS_EVIDENCE_KEY,
    CONTROL_EVIDENCE_KEY,
    EARNED_EVIDENCE_KEYS,
    READ_MODEL_EVIDENCE_KEY,
    TELEMETRY_EVIDENCE_KEY,
    VIEWS_EVIDENCE_KEY,
    prove_session_12,
)
from money_machine.control.state import (
    SESSION_EVIDENCE_KEYS,
    ControlState,
    ControlStateError,
    apply_session_12_evidence_record_transition,
    validate_session_12_evidence_record,
)

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
EARNED_AT = "2026-10-17T13:30:00Z"
_CONTROL_NAMES = (
    "IMPLEMENTATION_LOG.md",
    "DECISIONS.md",
    "TEST_EVIDENCE.md",
    "NEXT_SESSION.md",
)


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _false_pointer() -> ControlState:
    """Revision 95, rebuilt after the control-file record replaces the live file."""
    state = _live()
    state["state_revision"] = 95
    state["current_session"] = 12
    state["session_status"] = "incomplete"
    state["updated_at"] = "2026-10-17T13:25:00Z"
    evidence = dict.fromkeys(sorted(SESSION_EVIDENCE_KEYS[12]), False)
    evidence[READ_MODEL_EVIDENCE_KEY] = True
    evidence[VIEWS_EVIDENCE_KEY] = True
    evidence[TELEMETRY_EVIDENCE_KEY] = True
    evidence[ACTIONS_EVIDENCE_KEY] = True
    state["required_completion_evidence"] = evidence
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


def _write(path: Path, state: ControlState) -> None:
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def test_proof_earns_the_read_model_key() -> None:
    assert prove_session_12() == EARNED_EVIDENCE_KEYS
    assert READ_MODEL_EVIDENCE_KEY in EARNED_EVIDENCE_KEYS
    assert VIEWS_EVIDENCE_KEY in EARNED_EVIDENCE_KEYS
    assert TELEMETRY_EVIDENCE_KEY in EARNED_EVIDENCE_KEYS
    assert ACTIONS_EVIDENCE_KEY in EARNED_EVIDENCE_KEYS
    assert CONTROL_EVIDENCE_KEY in EARNED_EVIDENCE_KEYS


def test_the_read_model_key_is_the_accepted_record() -> None:
    previous = _false_pointer()
    validate_session_12_evidence_record(previous, _earned(previous))


def test_a_later_key_is_refused() -> None:
    previous = _false_pointer()
    current = _earned(previous)
    evidence = dict(current["required_completion_evidence"])
    evidence["evidence_closure_commit_recorded"] = True
    current["required_completion_evidence"] = evidence

    with pytest.raises(ControlStateError, match="the closure key stays false"):
        validate_session_12_evidence_record(previous, current)


def test_an_unknown_key_is_refused() -> None:
    previous = _false_pointer()
    current = _earned(previous)
    evidence = dict(current["required_completion_evidence"])
    evidence["live_posthog"] = True
    current["required_completion_evidence"] = evidence

    with pytest.raises(ControlStateError, match="missing or unsupported"):
        validate_session_12_evidence_record(previous, current)


def test_the_closure_key_is_refused() -> None:
    previous = _false_pointer()
    current = _earned(previous)
    evidence = dict(current["required_completion_evidence"])
    evidence["evidence_closure_commit_recorded"] = True
    current["required_completion_evidence"] = evidence

    with pytest.raises(ControlStateError, match="the closure key stays false"):
        validate_session_12_evidence_record(previous, current)


def test_apply_records_the_read_model_key_without_touching_the_live_file(tmp_path: Path) -> None:
    live_bytes = STATE_PATH.read_bytes()
    previous = _false_pointer()
    repo = tmp_path / "repository"
    control = repo / "docs" / "control"
    control.mkdir(parents=True)
    state_path = control / "IMPLEMENTATION_STATE.json"
    _write(state_path, previous)
    for name in _CONTROL_NAMES:
        (control / name).write_text("fixture\n", encoding="utf-8")
    subprocess.run(
        ["git", "-C", str(repo), "init", "-b", "fixture"], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.name", "Control Test"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "control-test@example.invalid"],
        check=True,
        capture_output=True,
    )
    subprocess.run(["git", "-C", str(repo), "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "commit", "-m", "fixture"],
        check=True,
        capture_output=True,
    )
    candidate = tmp_path / "candidate.json"
    _write(candidate, _earned(previous))

    applied = apply_session_12_evidence_record_transition(state_path, candidate)

    evidence = applied["required_completion_evidence"]
    assert applied["current_session"] == 12
    assert applied["session_status"] == "incomplete"
    assert applied["state_revision"] == previous["state_revision"] + 1
    assert applied["head_sha"] == previous["head_sha"]
    assert evidence[READ_MODEL_EVIDENCE_KEY] is True
    assert evidence[VIEWS_EVIDENCE_KEY] is True
    assert evidence[TELEMETRY_EVIDENCE_KEY] is True
    assert evidence[ACTIONS_EVIDENCE_KEY] is True
    assert evidence[CONTROL_EVIDENCE_KEY] is True
    assert evidence["evidence_closure_commit_recorded"] is False
    assert STATE_PATH.read_bytes() == live_bytes
