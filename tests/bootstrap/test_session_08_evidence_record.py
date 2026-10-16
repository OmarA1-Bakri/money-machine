"""Session 08 keys flip only through the proof-gated evidence transition."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import cast

import pytest

from money_machine.control.session_08_proof import (
    BEHAVIORAL_EVIDENCE_KEYS,
    CLOSURE_EVIDENCE_KEY,
    CONTROL_EVIDENCE_KEY,
)
from money_machine.control.state import (
    ControlState,
    ControlStateError,
    apply_active_evidence_record_transition,
    apply_session_08_evidence_record_transition,
    validate_session_08_evidence_record,
)

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
EARNED_AT = "2026-10-16T22:00:00Z"
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
    """Incomplete Session 08 with every key false.

    The live file may already record earned keys. These tests still start from
    the false map `record-evidence` is allowed to change.
    """
    state = _live()
    state["current_session"] = 8
    state["session_status"] = "incomplete"
    state["next_session"] = 8
    state["completed_sessions"] = [0, 1, 2, 3, 4, 5, 6, 7]
    keys = set(BEHAVIORAL_EVIDENCE_KEYS) | {CONTROL_EVIDENCE_KEY, CLOSURE_EVIDENCE_KEY}
    state["required_completion_evidence"] = dict.fromkeys(sorted(keys), False)
    state["updated_at"] = "2026-10-16T20:00:00Z"
    return state


def _advance(previous: ControlState, updated_at: str) -> ControlState:
    current = copy.deepcopy(previous)
    current["state_revision"] = previous["state_revision"] + 1
    current["updated_at"] = updated_at
    return current


def _eleven(previous: ControlState) -> ControlState:
    current = _advance(previous, EARNED_AT)
    evidence = dict(current["required_completion_evidence"])
    for key in BEHAVIORAL_EVIDENCE_KEYS | {CONTROL_EVIDENCE_KEY}:
        evidence[key] = True
    evidence[CLOSURE_EVIDENCE_KEY] = False
    current["required_completion_evidence"] = evidence
    return current


def _write(path: Path, state: ControlState) -> None:
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _git(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    ).stdout.strip()


def _repo(tmp_path: Path, state: ControlState) -> Path:
    repo = tmp_path / "repository"
    control = repo / "docs" / "control"
    control.mkdir(parents=True)
    state_path = control / "IMPLEMENTATION_STATE.json"
    _write(state_path, state)
    for name in _CONTROL_NAMES:
        (control / name).write_text("fixture\n", encoding="utf-8")
    _git(repo, "init", "-b", "fixture")
    _git(repo, "config", "user.name", "Control Test")
    _git(repo, "config", "user.email", "control-test@example.invalid")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "fixture")
    return state_path


def test_one_behavioral_key_is_refused() -> None:
    previous = _false_pointer()
    current = _advance(previous, EARNED_AT)
    evidence = dict(current["required_completion_evidence"])
    evidence["merchandising_agent_implemented"] = True
    current["required_completion_evidence"] = evidence

    with pytest.raises(ControlStateError, match="every key the fixture proof earned"):
        validate_session_08_evidence_record(previous, current)


def test_the_closure_key_is_refused() -> None:
    previous = _false_pointer()
    current = _eleven(previous)
    evidence = dict(current["required_completion_evidence"])
    evidence[CLOSURE_EVIDENCE_KEY] = True
    current["required_completion_evidence"] = evidence

    with pytest.raises(ControlStateError, match="the closure key stays false"):
        validate_session_08_evidence_record(previous, current)


def test_a_true_key_cannot_be_revoked() -> None:
    previous = _false_pointer()
    evidence = dict(previous["required_completion_evidence"])
    evidence["claim_validation_implemented"] = True
    previous["required_completion_evidence"] = evidence
    current = _advance(previous, EARNED_AT)
    current_evidence = dict(current["required_completion_evidence"])
    current_evidence["claim_validation_implemented"] = False
    current["required_completion_evidence"] = current_evidence

    with pytest.raises(ControlStateError, match="cannot revoke"):
        validate_session_08_evidence_record(previous, current)


def test_already_true_keys_must_flip_together() -> None:
    previous = _false_pointer()
    evidence = dict(previous["required_completion_evidence"])
    evidence["design_tokens_implemented"] = True
    previous["required_completion_evidence"] = evidence

    with pytest.raises(ControlStateError, match="flip every earned key together"):
        validate_session_08_evidence_record(previous, _eleven(previous))


def test_revision_must_advance_once() -> None:
    previous = _false_pointer()
    current = copy.deepcopy(previous)
    current["updated_at"] = EARNED_AT

    with pytest.raises(ControlStateError, match="state revision must advance exactly once"):
        validate_session_08_evidence_record(previous, current)


def test_updated_at_must_change() -> None:
    previous = _false_pointer()
    current = _eleven(previous)
    current["updated_at"] = previous["updated_at"]

    with pytest.raises(ControlStateError, match="updated_at must change"):
        validate_session_08_evidence_record(previous, current)


def test_session_must_stay_eight_and_incomplete() -> None:
    previous = _false_pointer()
    moved = _eleven(previous)
    moved["current_session"] = 7
    complete = _eleven(previous)
    complete["session_status"] = "complete"

    with pytest.raises(ControlStateError, match="only session 08"):
        validate_session_08_evidence_record(previous, moved)
    with pytest.raises(ControlStateError, match="must stay incomplete"):
        validate_session_08_evidence_record(previous, complete)


def test_head_sha_and_closure_sha_stay_put() -> None:
    previous = _false_pointer()
    moved_head = _eleven(previous)
    moved_head["head_sha"] = "c" * 40
    moved_closure = _eleven(previous)
    moved_closure["evidence_closure_commit_sha"] = "d" * 40

    with pytest.raises(ControlStateError, match="head_sha cannot change"):
        validate_session_08_evidence_record(previous, moved_head)
    with pytest.raises(ControlStateError, match="evidence_closure_commit_sha cannot change"):
        validate_session_08_evidence_record(previous, moved_closure)


def test_eleven_key_shape_is_accepted_and_an_empty_flip_is_not() -> None:
    previous = _false_pointer()
    validate_session_08_evidence_record(previous, _eleven(previous))
    empty = _advance(previous, EARNED_AT)

    with pytest.raises(ControlStateError, match="at least one key"):
        validate_session_08_evidence_record(previous, empty)


def test_missing_control_file_is_refused_before_the_proof(tmp_path: Path) -> None:
    live_bytes = STATE_PATH.read_bytes()
    previous = _false_pointer()
    state_path = _repo(tmp_path, previous)
    (state_path.parent / "NEXT_SESSION.md").unlink()
    candidate = tmp_path / "candidate.json"
    _write(candidate, _eleven(previous))

    with pytest.raises(ControlStateError, match="control files are missing"):
        apply_session_08_evidence_record_transition(state_path, candidate)

    stored = json.loads(state_path.read_text(encoding="utf-8"))
    assert stored["state_revision"] == previous["state_revision"]
    assert STATE_PATH.read_bytes() == live_bytes


def test_record_evidence_earns_the_eleven_keys(tmp_path: Path) -> None:
    live_bytes = STATE_PATH.read_bytes()
    previous = _false_pointer()
    state_path = _repo(tmp_path, previous)
    candidate = tmp_path / "candidate.json"
    proposed = _eleven(previous)
    _write(candidate, proposed)

    applied = apply_active_evidence_record_transition(state_path, candidate)

    evidence = applied["required_completion_evidence"]
    assert applied["current_session"] == 8
    assert applied["session_status"] == "incomplete"
    assert applied["state_revision"] == previous["state_revision"] + 1
    assert applied["head_sha"] == previous["head_sha"]
    assert applied["evidence_closure_commit_sha"] == previous["evidence_closure_commit_sha"]
    assert evidence[CLOSURE_EVIDENCE_KEY] is False
    assert all(evidence[key] is True for key in BEHAVIORAL_EVIDENCE_KEYS | {CONTROL_EVIDENCE_KEY})
    assert STATE_PATH.read_bytes() == live_bytes


def test_dispatch_refuses_a_session_that_cannot_record(tmp_path: Path) -> None:
    previous = _false_pointer()
    previous["current_session"] = 9
    state_path = tmp_path / "state.json"
    _write(state_path, previous)
    candidate = tmp_path / "candidate.json"
    _write(candidate, _eleven(previous))

    with pytest.raises(ControlStateError, match="only session 07 or incomplete session 08"):
        apply_active_evidence_record_transition(state_path, candidate)

    assert state_path.read_bytes() == json.dumps(previous, indent=2).encode("utf-8") + b"\n"
