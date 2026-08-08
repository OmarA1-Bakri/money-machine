from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

import pytest

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
CONTROL_FILES = {
    "IMPLEMENTATION_STATE.json",
    "IMPLEMENTATION_LOG.md",
    "DECISIONS.md",
    "TEST_EVIDENCE.md",
    "NEXT_SESSION.md",
}
BRANCH = "build/full-automation"
BOOTSTRAP_SUBJECT = "chore(bootstrap): initialise money machine autonomous monorepo"
OUTER_GATES_BLOCKER = "SESSION_00_OUTER_GATES_PENDING"
CLOSURE_EVIDENCE_KEY = "evidence_closure_commit_recorded"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


class ControlState(TypedDict):
    repo_root: str
    branch: str
    session_status: str
    state_revision: int
    current_session: int
    completed_sessions: list[int]
    next_session: int
    next_prompt: str
    bootstrap_commit_sha: str | None
    evidence_closure_commit_sha: str | None
    last_verified_commit: str | None
    head_sha: str | None
    services: dict[str, str]
    commissioned_agents: list[str]
    tests: dict[str, str]
    environment_versions: dict[str, str]
    blockers: list[dict[str, str]]
    required_completion_evidence: dict[str, bool]
    transition_contract: dict[str, bool | int]
    updated_at: str


@dataclass(frozen=True)
class GitTransition:
    repo: Path
    state_path: Path
    candidate_path: Path
    candidate: ControlState
    bootstrap: str
    closure: str


Mutation = Callable[[ControlState], None]


def load_state(path: Path = STATE_PATH) -> ControlState:
    return cast(ControlState, json.loads(path.read_text(encoding="utf-8")))


def load_document(path: Path) -> dict[str, object]:
    return cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))


def write_state(path: Path, state: ControlState) -> None:
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def write_document(path: Path, document: dict[str, object]) -> None:
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def incomplete_session_zero_fixture() -> ControlState:
    state = copy.deepcopy(load_state())
    state.update(
        {
            "session_status": "incomplete",
            "current_session": 0,
            "completed_sessions": [],
            "next_session": 0,
            "next_prompt": "03_SESSION_00_DISCOVERY_AND_REPO_BOOTSTRAP.md",
            "head_sha": None,
            "bootstrap_commit_sha": None,
            "evidence_closure_commit_sha": None,
            "last_verified_commit": None,
            "updated_at": "2026-08-08T00:00:00Z",
        }
    )
    state["blockers"] = [
        blocker for blocker in state["blockers"] if blocker["code"] != OUTER_GATES_BLOCKER
    ]
    state["blockers"].append(
        {
            "code": OUTER_GATES_BLOCKER,
            "scope": "session completion",
            "detail": "Fixture awaits the evidence-closure transition.",
        }
    )
    return state


def git(repo: Path, *arguments: str, stdin: str | None = None) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        input=stdin,
    ).stdout.strip()


def completed_candidate(state: ControlState, bootstrap: str, closure: str) -> ControlState:
    candidate = copy.deepcopy(state)
    candidate.update(
        {
            "state_revision": state["state_revision"] + 1,
            "session_status": "complete",
            "completed_sessions": [0],
            "next_session": 1,
            "next_prompt": "04_SESSION_01_PLAYBOOK_MAPPING_AND_ARCHITECTURE.md",
            "bootstrap_commit_sha": bootstrap,
            "evidence_closure_commit_sha": closure,
            "last_verified_commit": bootstrap,
            "head_sha": closure,
            "updated_at": "2026-08-09T00:00:00Z",
        }
    )
    candidate["required_completion_evidence"] = {
        key: True for key in candidate["required_completion_evidence"]
    }
    candidate["blockers"] = [
        blocker for blocker in candidate["blockers"] if blocker["code"] != OUTER_GATES_BLOCKER
    ]
    return candidate


def run_transition(state_path: Path, candidate_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "money_machine.control",
            "apply-completion",
            "--state",
            str(state_path),
            "--candidate",
            str(candidate_path),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def prepare_transition(tmp_path: Path) -> GitTransition:
    repo = tmp_path / "repository"
    state_path = repo / "docs/control/IMPLEMENTATION_STATE.json"
    state_path.parent.mkdir(parents=True)
    state = incomplete_session_zero_fixture()
    state["repo_root"] = str(repo)
    state["branch"] = BRANCH
    write_state(state_path, state)
    evidence_path = repo / "evidence.txt"
    evidence_path.write_text("reviewed evidence\n", encoding="utf-8")

    git(repo, "init", "-b", BRANCH)
    git(repo, "config", "user.name", "Control Test")
    git(repo, "config", "user.email", "control-test@example.invalid")
    git(repo, "add", "docs/control/IMPLEMENTATION_STATE.json", "evidence.txt")
    git(repo, "commit", "-m", BOOTSTRAP_SUBJECT)
    bootstrap = git(repo, "rev-parse", "HEAD")

    state.update(
        {
            "head_sha": bootstrap,
            "bootstrap_commit_sha": bootstrap,
            "last_verified_commit": bootstrap,
            "evidence_closure_commit_sha": None,
        }
    )
    state["required_completion_evidence"] = {
        key: key != CLOSURE_EVIDENCE_KEY for key in state["required_completion_evidence"]
    }
    write_state(state_path, state)
    git(repo, "add", "docs/control/IMPLEMENTATION_STATE.json")
    git(repo, "commit", "-m", "chore(control): close bootstrap evidence")
    closure = git(repo, "rev-parse", "HEAD")

    candidate = completed_candidate(state, bootstrap, closure)
    candidate_path = tmp_path / "candidate.json"
    write_state(candidate_path, candidate)
    return GitTransition(repo, state_path, candidate_path, candidate, bootstrap, closure)


def test_control_files_are_exactly_the_five_continuity_files() -> None:
    assert {
        path.name for path in (ROOT / "docs/control").iterdir() if path.is_file()
    } == CONTROL_FILES


def test_checked_in_state_is_a_valid_session_zero_continuity_shape() -> None:
    state = load_state()
    required = {
        "programme",
        "version",
        "repo_root",
        "windows_repo_root",
        "branch",
        "head_sha",
        "current_session",
        "completed_sessions",
        "services",
        "commissioned_agents",
        "tests",
        "environment_versions",
        "blockers",
        "next_session",
        "updated_at",
        "required_completion_evidence",
        "transition_contract",
    }
    assert required <= state.keys()
    assert state["current_session"] == 0
    if state["session_status"] == "incomplete":
        assert state["completed_sessions"] == []
        assert state["next_session"] == 0
        assert not all(state["required_completion_evidence"].values())
    else:
        assert state["session_status"] == "complete"
        assert state["completed_sessions"] == [0]
        assert state["next_session"] == 1
        assert state["next_prompt"] == "04_SESSION_01_PLAYBOOK_MAPPING_AND_ARCHITECTURE.md"
        assert all(state["required_completion_evidence"].values())
        bootstrap = state["bootstrap_commit_sha"]
        closure = state["evidence_closure_commit_sha"]
        assert FULL_SHA.fullmatch(bootstrap or "")
        assert FULL_SHA.fullmatch(closure or "")
        assert bootstrap != closure
        assert state["last_verified_commit"] == bootstrap
        assert state["head_sha"] == closure


def test_real_entrypoint_atomically_applies_git_backed_transition(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["applied"] is True
    assert load_state(transition.state_path) == transition.candidate
    assert git(transition.repo, "rev-parse", "HEAD") == transition.closure
    assert git(
        transition.repo, "status", "--porcelain", "--", "docs/control/IMPLEMENTATION_STATE.json"
    )
    assert not list(transition.state_path.parent.glob(".IMPLEMENTATION_STATE.json.*.tmp"))


@pytest.mark.parametrize(
    "fabricated_evidence",
    [
        "implementation_review_approved",
        "adversarial_review_clear",
        "bootstrap_commit_recorded",
        "api_health_live",
    ],
)
def test_rejects_candidate_fabricating_pre_transition_evidence_without_writing(
    tmp_path: Path,
    fabricated_evidence: str,
) -> None:
    transition = prepare_transition(tmp_path)
    previous = load_state(transition.state_path)
    previous["required_completion_evidence"][fabricated_evidence] = False
    write_state(transition.state_path, previous)
    original = transition.state_path.read_bytes()

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "pre-transition evidence must be complete except" in result.stderr
    assert transition.state_path.read_bytes() == original


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("services", {"api": "fabricated_green"}),
        ("tests", {"all": "fabricated_green"}),
        ("environment_versions", {"python": "fabricated"}),
        ("transition_contract", {"unsupported_completion_is_rejected": False}),
        ("commissioned_agents", ["fabricated-agent"]),
    ],
)
def test_rejects_candidate_rewriting_continuity_evidence_without_writing(
    tmp_path: Path,
    field: str,
    replacement: object,
) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    candidate = cast(dict[str, object], transition.candidate)
    candidate[field] = replacement
    write_state(transition.candidate_path, transition.candidate)

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert f"{field} cannot change" in result.stderr
    assert transition.state_path.read_bytes() == original


@pytest.mark.parametrize("mutation", ["remove", "rewrite", "add"])
def test_rejects_unauthorized_blocker_changes_without_writing(
    tmp_path: Path,
    mutation: str,
) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    blockers = transition.candidate["blockers"]
    if mutation == "remove":
        blockers.clear()
    elif mutation == "rewrite":
        blockers[0]["detail"] = "fabricated resolution"
    else:
        blockers.append({"code": "FABRICATED_BLOCKER", "scope": "session", "detail": "unsupported"})
    write_state(transition.candidate_path, transition.candidate)

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "may remove only the Session 00 outer-gates blocker" in result.stderr
    assert transition.state_path.read_bytes() == original


@pytest.mark.parametrize(
    ("field", "invalid_value", "expected"),
    [
        ("bootstrap_commit_sha", "not-a-sha", "bootstrap_commit_sha must be"),
        ("last_verified_commit", "b" * 40, "last_verified_commit must identify"),
        ("head_sha", "b" * 40, "head_sha must identify the bootstrap"),
        (
            "evidence_closure_commit_sha",
            "b" * 40,
            "pre-transition evidence_closure_commit_sha must be null",
        ),
    ],
)
def test_rejects_invalid_pre_transition_commit_semantics_without_writing(
    tmp_path: Path,
    field: str,
    invalid_value: str,
    expected: str,
) -> None:
    transition = prepare_transition(tmp_path)
    previous = load_state(transition.state_path)
    previous[field] = invalid_value
    transition.candidate[field] = invalid_value
    if field == "evidence_closure_commit_sha":
        transition.candidate[field] = transition.closure
    write_state(transition.state_path, previous)
    write_state(transition.candidate_path, transition.candidate)
    original = transition.state_path.read_bytes()

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert expected in result.stderr
    assert transition.state_path.read_bytes() == original


def test_rejects_closure_commit_document_mismatch_without_writing(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    previous = load_state(transition.state_path)
    previous["tests"]["closure_document_probe"] = "present_only_after_closure"
    transition.candidate["tests"] = copy.deepcopy(previous["tests"])
    write_state(transition.state_path, previous)
    git(
        transition.repo,
        "update-index",
        "--assume-unchanged",
        "docs/control/IMPLEMENTATION_STATE.json",
    )
    write_state(transition.candidate_path, transition.candidate)
    original = transition.state_path.read_bytes()

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "evidence-closure commit must contain the exact pre-transition state" in result.stderr
    assert transition.state_path.read_bytes() == original


def mark_api_health_incomplete(candidate: ControlState) -> None:
    candidate["required_completion_evidence"]["api_health_live"] = False


def remove_evidence_key(candidate: ControlState) -> None:
    del candidate["required_completion_evidence"]["api_health_live"]


def duplicate_completed_session(candidate: ControlState) -> None:
    candidate["completed_sessions"] = [0, 0]


def skip_next_session(candidate: ControlState) -> None:
    candidate["next_session"] = 2


def reuse_bootstrap_commit(candidate: ControlState) -> None:
    candidate["evidence_closure_commit_sha"] = candidate["bootstrap_commit_sha"]
    candidate["head_sha"] = candidate["bootstrap_commit_sha"]


def skip_state_revision(candidate: ControlState) -> None:
    candidate["state_revision"] = 9


def use_unsupported_completion(candidate: ControlState) -> None:
    candidate["session_status"] = "commissioned"


def use_wrong_session_one_prompt(candidate: ControlState) -> None:
    candidate["next_prompt"] = "04_SESSION_01_WRONG_PROMPT.md"


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (mark_api_health_incomplete, "cannot change except"),
        (remove_evidence_key, "evidence keys"),
        (duplicate_completed_session, "completed_sessions"),
        (skip_next_session, "next session"),
        (reuse_bootstrap_commit, "must be distinct"),
        (skip_state_revision, "revision"),
        (use_unsupported_completion, "unsupported completion"),
        (use_wrong_session_one_prompt, "canonical Session 01 prompt"),
    ],
)
def test_real_entrypoint_rejects_invalid_transition_without_writing(
    tmp_path: Path,
    mutation: Mutation,
    expected: str,
) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    mutation(transition.candidate)
    write_state(transition.candidate_path, transition.candidate)

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert expected in result.stderr
    assert transition.state_path.read_bytes() == original
    assert not list(transition.state_path.parent.glob(".IMPLEMENTATION_STATE.json.*.tmp"))


def test_rejects_candidate_reusing_previous_updated_at_without_writing(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    transition.candidate["updated_at"] = load_state(transition.state_path)["updated_at"]
    write_state(transition.candidate_path, transition.candidate)

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "updated_at must change" in result.stderr
    assert transition.state_path.read_bytes() == original


def test_rejects_nonexistent_commit_object(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    nonexistent = "c" * 40
    transition.candidate["evidence_closure_commit_sha"] = nonexistent
    transition.candidate["head_sha"] = nonexistent
    write_state(transition.candidate_path, transition.candidate)

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "Git verification failed" in result.stderr
    assert transition.state_path.read_bytes() == original


def test_rejects_bootstrap_commit_that_is_not_closure_ancestor(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    tree = git(transition.repo, "rev-parse", f"{transition.closure}^{{tree}}")
    unrelated = git(
        transition.repo,
        "commit-tree",
        tree,
        stdin=f"{BOOTSTRAP_SUBJECT}\n",
    )
    previous = load_state(transition.state_path)
    previous["bootstrap_commit_sha"] = unrelated
    previous["last_verified_commit"] = unrelated
    previous["head_sha"] = unrelated
    transition.candidate["bootstrap_commit_sha"] = unrelated
    transition.candidate["last_verified_commit"] = unrelated
    write_state(transition.state_path, previous)
    git(
        transition.repo,
        "update-index",
        "--assume-unchanged",
        "docs/control/IMPLEMENTATION_STATE.json",
    )
    write_state(transition.candidate_path, transition.candidate)
    original = transition.state_path.read_bytes()

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "must be an ancestor" in result.stderr
    assert transition.state_path.read_bytes() == original


def test_rejects_dirty_tracked_state_before_application(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    with transition.state_path.open("a", encoding="utf-8") as stream:
        stream.write("\n")
    dirty = transition.state_path.read_bytes()

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "must be clean" in result.stderr
    assert transition.state_path.read_bytes() == dirty


def test_rejects_dirty_non_state_tracked_file_before_application(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    evidence_path = transition.repo / "evidence.txt"
    evidence_path.write_text("locally changed evidence\n", encoding="utf-8")
    original = transition.state_path.read_bytes()

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "all tracked repository files must be clean" in result.stderr
    assert transition.state_path.read_bytes() == original


def test_rejects_candidates_missing_any_continuity_field_without_writing(
    tmp_path: Path,
) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    baseline = load_document(transition.candidate_path)
    continuity_fields = (
        "windows_repo_root",
        "services",
        "commissioned_agents",
        "tests",
        "blockers",
        "environment_versions",
        "transition_contract",
    )

    for field in continuity_fields:
        candidate = copy.deepcopy(baseline)
        del candidate[field]
        write_document(transition.candidate_path, candidate)

        result = run_transition(transition.state_path, transition.candidate_path)

        assert result.returncode == 2
        assert f"missing required fields: {field}" in result.stderr
        assert transition.state_path.read_bytes() == original


def test_rejects_invalid_nested_continuity_types_without_writing(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    baseline = load_document(transition.candidate_path)
    invalid_values: tuple[tuple[str, object, str], ...] = (
        ("services", {"api": 200}, "services must map string keys to string values"),
        ("commissioned_agents", [7], "commissioned_agents must be a list of strings"),
        ("tests", {"python": True}, "tests must map string keys to string values"),
        (
            "environment_versions",
            {"python": 3.12},
            "environment_versions must map string keys to string values",
        ),
        ("blockers", [{"code": "X", "scope": "all"}], "blockers must be a list"),
        (
            "transition_contract",
            {"completion_requires_next_session": "1"},
            "transition_contract must map strings to booleans or integers",
        ),
    )

    for field, invalid, expected in invalid_values:
        candidate = copy.deepcopy(baseline)
        candidate[field] = invalid
        write_document(transition.candidate_path, candidate)

        result = run_transition(transition.state_path, transition.candidate_path)

        assert result.returncode == 2
        assert expected in result.stderr
        assert transition.state_path.read_bytes() == original
