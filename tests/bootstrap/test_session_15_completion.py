"""Session 15 completion stays on session 15 and requires its proof."""

from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path
from typing import cast

import pytest

from money_machine.control.state import (
    BOOTSTRAP_COMMIT_SUBJECT,
    SESSION_PROMPTS,
    ControlState,
    ControlStateError,
    apply_completion_transition,
)
from money_machine.deploy.closure import ClosureRefusal, record_terminal_closure

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
COMPLETED_AT = "2026-10-17T16:50:00Z"
_RELEASE_SUBJECT = "chore(release): commission hands-off money machine"


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _completed(previous: ControlState, closure: str) -> ControlState:
    current = copy.deepcopy(previous)
    current["state_revision"] = previous["state_revision"] + 1
    current["session_status"] = "complete"
    current["completed_sessions"] = list(range(16))
    current["next_session"] = 15
    current["next_prompt"] = SESSION_PROMPTS[15]
    current["head_sha"] = closure
    current["evidence_closure_commit_sha"] = closure
    current["updated_at"] = COMPLETED_AT
    evidence = dict(current["required_completion_evidence"])
    evidence["evidence_closure_commit_recorded"] = True
    current["required_completion_evidence"] = evidence
    return current


def _git(repo: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    ).stdout.strip()


def _write(path: Path, state: ControlState) -> None:
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _closure_repo(
    tmp_path: Path,
    *,
    proof: str,
    message: str = "session 15 closure",
) -> tuple[Path, ControlState, str]:
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

    previous = _live()
    previous["repo_root"] = "/mnt/d/Money Machine"
    previous["branch"] = "build/full-automation"
    previous["bootstrap_commit_sha"] = bootstrap
    previous["last_verified_commit"] = bootstrap
    previous["head_sha"] = prior
    previous["evidence_closure_commit_sha"] = prior
    _write(state_path, previous)
    proof_path = repo / "src" / "money_machine" / "control" / "session_15_proof.py"
    proof_path.parent.mkdir(parents=True)
    proof_path.write_text(proof, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", message)
    closure = _git(repo, "rev-parse", "HEAD")
    return state_path, previous, closure


def test_absent_root_completion_stays_on_session_15(tmp_path: Path) -> None:
    state_path, previous, closure = _closure_repo(
        tmp_path,
        proof="def prove_session_15() -> None:\n    return None\n",
    )
    candidate = tmp_path / "candidate.json"
    _write(candidate, _completed(previous, closure))

    applied = apply_completion_transition(state_path, candidate)

    assert applied["session_status"] == "complete"
    assert applied["current_session"] == 15
    assert applied["next_session"] == 15
    assert applied["next_prompt"] == SESSION_PROMPTS[15]
    assert applied["completed_sessions"] == list(range(16))
    assert applied["head_sha"] == closure
    assert applied["evidence_closure_commit_sha"] == closure
    assert applied["required_completion_evidence"]["evidence_closure_commit_recorded"] is True
    text = state_path.read_text(encoding="utf-8")
    assert "HANDS_OFF_MONEY_MACHINE_COMMISSIONED" not in text
    assert "COMMISSIONED" not in text
    assert applied["repo_root"] == "/mnt/d/Money Machine"
    assert applied["branch"] == "build/full-automation"


def test_closure_without_the_session_15_proof_is_refused(tmp_path: Path) -> None:
    state_path, previous, closure = _closure_repo(
        tmp_path, proof="def unrelated() -> None:\n    return None\n"
    )
    original = state_path.read_bytes()
    candidate = tmp_path / "candidate.json"
    _write(candidate, _completed(previous, closure))

    with pytest.raises(ControlStateError, match="session 15 proof"):
        apply_completion_transition(state_path, candidate)

    assert state_path.read_bytes() == original


def test_a_release_subject_is_refused(tmp_path: Path) -> None:
    state_path, previous, closure = _closure_repo(
        tmp_path,
        proof="def prove_session_15() -> None:\n    return None\n",
        message=_RELEASE_SUBJECT,
    )
    original = state_path.read_bytes()
    candidate = tmp_path / "candidate.json"
    _write(candidate, _completed(previous, closure))

    with pytest.raises(ControlStateError, match="release"):
        apply_completion_transition(state_path, candidate)

    assert state_path.read_bytes() == original


def test_a_successor_session_is_refused(tmp_path: Path) -> None:
    state_path, previous, closure = _closure_repo(
        tmp_path,
        proof="def prove_session_15() -> None:\n    return None\n",
    )
    original = state_path.read_bytes()
    current = _completed(previous, closure)
    current["next_session"] = 16
    candidate = tmp_path / "candidate.json"
    _write(candidate, current)

    with pytest.raises(ControlStateError, match="no successor"):
        apply_completion_transition(state_path, candidate)

    assert state_path.read_bytes() == original


def test_the_terminal_closure_refuses_a_null_next_session() -> None:
    with pytest.raises(ClosureRefusal, match="next_session"):
        record_terminal_closure(
            status="complete",
            next_session=None,
            next_prompt=SESSION_PROMPTS[15],
            closure_recorded=True,
        )
