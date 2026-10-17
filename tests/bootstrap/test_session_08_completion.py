"""Session 08 completion may start from the frozen D-0032 pointer."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import cast

import pytest

from money_machine.control.state import (
    BOOTSTRAP_COMMIT_SUBJECT,
    SESSION_EVIDENCE_KEYS,
    SESSION_PROMPTS,
    ControlState,
    ControlStateError,
    apply_completion_transition,
    validate_completion_transition,
)

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
FROZEN_HEAD = "b782751fdb1b255c436ff7f6fa655e6d783b1e8c"
FROZEN_CLOSURE = "5a48a4c9c04c74019e382a62b2c3c0abfd5b9cfb"
NEW_CLOSURE = "6521794fdb1b255c436ff7f6fa655e6d783b1e8c"
COMPLETED_AT = "2026-10-17T09:49:00Z"


def _live() -> ControlState:
    """Return a deep copy of the checked-in implementation state."""
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _pre_completion() -> ControlState:
    """The revision-68 shape, even after the live file has moved on."""
    state = _live()
    state["current_session"] = 8
    state["session_status"] = "incomplete"
    state["completed_sessions"] = [0, 1, 2, 3, 4, 5, 6, 7]
    state["next_session"] = 8
    state["next_prompt"] = SESSION_PROMPTS[8]
    state["head_sha"] = FROZEN_HEAD
    state["evidence_closure_commit_sha"] = FROZEN_CLOSURE
    state["state_revision"] = 68
    state["updated_at"] = "2026-10-16T22:00:00Z"
    evidence = {key: True for key in SESSION_EVIDENCE_KEYS[8]}
    evidence["evidence_closure_commit_recorded"] = False
    state["required_completion_evidence"] = evidence
    contract = dict(state["transition_contract"])
    contract["completion_requires_next_session"] = 8
    state["transition_contract"] = contract
    return state


def _completed(previous: ControlState, closure: str) -> ControlState:
    """Return the Session 08 completion candidate that advances past ``previous`` to session 9."""
    current = copy.deepcopy(previous)
    current["state_revision"] = previous["state_revision"] + 1
    current["session_status"] = "complete"
    current["completed_sessions"] = [0, 1, 2, 3, 4, 5, 6, 7, 8]
    current["next_session"] = 9
    current["next_prompt"] = SESSION_PROMPTS[9]
    current["head_sha"] = closure
    current["evidence_closure_commit_sha"] = closure
    current["updated_at"] = COMPLETED_AT
    evidence = dict(current["required_completion_evidence"])
    evidence["evidence_closure_commit_recorded"] = True
    current["required_completion_evidence"] = evidence
    contract = dict(current["transition_contract"])
    contract["completion_requires_next_session"] = 9
    current["transition_contract"] = contract
    return current


def test_frozen_pair_completion_shape_is_accepted() -> None:
    """Completion validates when the frozen D-0032 head/closure mismatch is session 08's."""
    previous = _pre_completion()
    validate_completion_transition(previous, _completed(previous, NEW_CLOSURE))


def test_a_different_head_is_still_refused() -> None:
    """A head_sha that is neither the prior closure nor the frozen pair is refused."""
    previous = _pre_completion()
    previous["head_sha"] = "a" * 40

    with pytest.raises(ControlStateError, match="prior closure commit"):
        validate_completion_transition(previous, _completed(previous, NEW_CLOSURE))


def test_session_07_cannot_use_the_frozen_pair() -> None:
    """The frozen head/closure mismatch exception does not apply to session 07."""
    previous = _pre_completion()
    previous["current_session"] = 7
    previous["completed_sessions"] = [0, 1, 2, 3, 4, 5, 6]
    previous["required_completion_evidence"] = {
        key: key != "evidence_closure_commit_recorded" for key in SESSION_EVIDENCE_KEYS[7]
    }
    current = _completed(previous, NEW_CLOSURE)
    current["current_session"] = 7
    current["required_completion_evidence"] = dict.fromkeys(SESSION_EVIDENCE_KEYS[7], True)
    current["completed_sessions"] = [0, 1, 2, 3, 4, 5, 6, 7]
    current["next_session"] = 8
    current["next_prompt"] = SESSION_PROMPTS[8]
    contract = dict(current["transition_contract"])
    contract["completion_requires_next_session"] = 8
    current["transition_contract"] = contract

    with pytest.raises(ControlStateError, match="prior closure commit"):
        validate_completion_transition(previous, current)


def test_reusing_the_prior_closure_is_refused() -> None:
    """Completion requires a new evidence-closure commit, not the prior one reused."""
    previous = _pre_completion()

    with pytest.raises(ControlStateError, match="new evidence-closure commit"):
        validate_completion_transition(previous, _completed(previous, FROZEN_CLOSURE))


def _git(repo: Path, *arguments: str) -> str:
    """Run a Git command in ``repo`` and return its trimmed stdout."""
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    ).stdout.strip()


def _write(path: Path, state: ControlState) -> None:
    """Write ``state`` as indented JSON to ``path``."""
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _closure_repo(tmp_path: Path, *, proof: str) -> tuple[Path, ControlState, str]:
    """Build a fixture repository with a bootstrap, prior closure, and new closure commit."""
    repo = tmp_path / "repository"
    control = repo / "docs" / "control"
    control.mkdir(parents=True)
    state_path = control / "IMPLEMENTATION_STATE.json"
    _git(repo, "init", "-b", "fixture")
    _git(repo, "config", "user.name", "Control Test")
    _git(repo, "config", "user.email", "control-test@example.invalid")
    (repo / "README.md").write_text("bootstrap\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", BOOTSTRAP_COMMIT_SUBJECT)
    bootstrap = _git(repo, "rev-parse", "HEAD")
    (repo / "prior.txt").write_text("prior\n", encoding="utf-8")
    _git(repo, "add", "prior.txt")
    _git(repo, "commit", "-m", "prior closure")
    prior = _git(repo, "rev-parse", "HEAD")

    previous = _pre_completion()
    previous["repo_root"] = "/mnt/d/Money Machine"
    previous["branch"] = "build/full-automation"
    previous["bootstrap_commit_sha"] = bootstrap
    previous["last_verified_commit"] = bootstrap
    previous["head_sha"] = prior
    previous["evidence_closure_commit_sha"] = prior
    _write(state_path, previous)
    proof_path = repo / "src" / "money_machine" / "control" / "session_08_proof.py"
    proof_path.parent.mkdir(parents=True)
    proof_path.write_text(proof, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "session 08 closure")
    closure = _git(repo, "rev-parse", "HEAD")
    return state_path, previous, closure


def test_absent_root_completion_records_the_closure(tmp_path: Path) -> None:
    """Completion succeeds against the canonical worktree when the recorded root is absent."""
    state_path, previous, closure = _closure_repo(
        tmp_path,
        proof="def prove_session_08() -> None:\n    return None\n",
    )
    candidate = tmp_path / "candidate.json"
    _write(candidate, _completed(previous, closure))

    applied = apply_completion_transition(state_path, candidate)

    assert applied["session_status"] == "complete"
    assert applied["current_session"] == 8
    assert applied["next_session"] == 9
    assert applied["head_sha"] == closure
    assert applied["evidence_closure_commit_sha"] == closure
    assert applied["required_completion_evidence"]["evidence_closure_commit_recorded"] is True
    assert applied["repo_root"] == "/mnt/d/Money Machine"
    assert applied["branch"] == "build/full-automation"


def test_closure_without_the_session_08_proof_is_refused(tmp_path: Path) -> None:
    """A closure commit without the session 08 proof module is refused; state is untouched."""
    state_path, previous, closure = _closure_repo(
        tmp_path, proof="def unrelated() -> None:\n    return None\n"
    )
    original = state_path.read_bytes()
    candidate = tmp_path / "candidate.json"
    _write(candidate, _completed(previous, closure))

    with pytest.raises(ControlStateError, match="session 08 proof"):
        apply_completion_transition(state_path, candidate)

    assert state_path.read_bytes() == original
