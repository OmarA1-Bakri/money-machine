from __future__ import annotations

import copy
import json
import logging
import os
import re
import subprocess
import sys
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict, cast

import pytest

from money_machine.control import state as control_state

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


SESSION_00_EVIDENCE_KEYS = (
    "canonical_root_verified",
    "canonical_scaffold_verified",
    "sources_byte_identical",
    "pdf_pages_1_through_82_mapped",
    "required_playbook_items_mapped",
    "prompt_pack_verified",
    "git_ignore_audit_passed",
    "environment_versions_recorded",
    "git_evidence_semantics_verified",
    "python_checks_passed",
    "web_checks_passed",
    "compose_postgres_healthy",
    "api_health_live",
    "scripts_parse",
    "clean_bootstrap_passed",
    "implementation_review_approved",
    "adversarial_review_clear",
    "bootstrap_commit_recorded",
    CLOSURE_EVIDENCE_KEY,
)


def incomplete_session_zero_fixture() -> ControlState:
    """Session 00 pre-completion shape, independent of the live state's current session."""
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
    state["required_completion_evidence"] = dict.fromkeys(SESSION_00_EVIDENCE_KEYS, False)
    # The live state advances with the programme; these fixtures must describe Session 00 only.
    state["transition_contract"] = {
        **state["transition_contract"],
        "completion_requires_next_session": 1,
    }
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
        encoding="utf-8",
        input=stdin,
        timeout=control_state.GIT_TIMEOUT_SECONDS,
    ).stdout.strip()


def completed_candidate(state: ControlState, bootstrap: str, closure: str) -> ControlState:
    candidate = copy.deepcopy(state)
    candidate["transition_contract"] = {
        **state["transition_contract"],
        "completion_requires_next_session": 1,
    }
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


def run_transition(
    state_path: Path,
    candidate_path: Path,
    command: str = "apply-completion",
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "money_machine.control",
            command,
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


def test_checked_in_state_is_a_valid_session_continuity_shape() -> None:
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
    session = state["current_session"]
    assert session in control_state.SESSION_PROMPTS
    if state["session_status"] == "incomplete":
        assert state["completed_sessions"] == list(range(session))
        assert state["next_session"] == session
        assert state["next_prompt"] == control_state.SESSION_PROMPTS[session]
        evidence = state["required_completion_evidence"]
        assert evidence.keys() == control_state.SESSION_EVIDENCE_KEYS[session]
        assert evidence[CLOSURE_EVIDENCE_KEY] is False
    else:
        assert state["session_status"] == "complete"
        assert state["completed_sessions"] == list(range(session + 1))
        assert state["next_session"] == session + 1
        assert state["next_prompt"] == control_state.SESSION_PROMPTS[session + 1]
        evidence = state["required_completion_evidence"]
        assert evidence.keys() == control_state.SESSION_EVIDENCE_KEYS[session]
        assert all(evidence.values())
    if session >= 0 and state["bootstrap_commit_sha"] is not None:
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


def test_git_uses_bounded_utf8_subprocess(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    invocation: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        invocation["args"] = args
        invocation["kwargs"] = kwargs
        return subprocess.CompletedProcess(["git"], 0, stdout="", stderr="")

    monkeypatch.setattr(control_state.subprocess, "run", fake_run)
    git_runner = control_state._git  # pyright: ignore[reportPrivateUsage]

    git_runner(tmp_path, "status")

    kwargs = cast(dict[str, object], invocation["kwargs"])
    assert kwargs["timeout"] == control_state.GIT_TIMEOUT_SECONDS
    assert kwargs["encoding"] == "utf-8"
    assert kwargs["text"] is True


def test_git_timeout_is_a_control_state_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def time_out(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        raise subprocess.TimeoutExpired(["git", "status"], timeout=1)

    monkeypatch.setattr(control_state.subprocess, "run", time_out)
    git_runner = control_state._git  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(control_state.ControlStateError, match="Git command timed out"):
        git_runner(tmp_path, "status")


def test_atomic_write_closes_raw_descriptor_when_fdopen_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "state.json"
    temporary = tmp_path / ".state.json.failed.tmp"
    descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)

    def fake_mkstemp(**kwargs: object) -> tuple[int, str]:
        del kwargs
        return descriptor, str(temporary)

    monkeypatch.setattr(control_state.tempfile, "mkstemp", fake_mkstemp)

    def fail_fdopen(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise OSError("fdopen failed")

    monkeypatch.setattr(control_state.os, "fdopen", fail_fdopen)
    atomic_writer = control_state._atomic_write_json  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(OSError, match="fdopen failed"):
        atomic_writer(target, {"state": "candidate"})

    with pytest.raises(OSError):
        os.fstat(descriptor)
    assert not temporary.exists()


def test_atomic_write_works_without_fchmod(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = tmp_path / "state.json"
    target.write_text('{"state": "previous"}\n', encoding="utf-8")
    monkeypatch.delattr(control_state.os, "fchmod", raising=False)
    atomic_writer = control_state._atomic_write_json  # pyright: ignore[reportPrivateUsage]

    atomic_writer(target, {"state": "candidate"})

    assert json.loads(target.read_text(encoding="utf-8")) == {"state": "candidate"}


def test_transition_fails_closed_when_sibling_lock_exists(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    original = transition.state_path.read_bytes()
    lock_path = transition.state_path.with_name(f".{transition.state_path.name}.lock")
    lock_path.write_text("held\n", encoding="utf-8")

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "state transition lock" in result.stderr
    assert transition.state_path.read_bytes() == original
    assert lock_path.read_text(encoding="utf-8") == "held\n"


def test_transition_removes_sibling_lock_after_success(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    lock_path = transition.state_path.with_name(f".{transition.state_path.name}.lock")

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 0, result.stderr
    assert not lock_path.exists()


def test_transition_removes_sibling_lock_after_validation_failure(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    transition.candidate["state_revision"] += 1
    write_state(transition.candidate_path, transition.candidate)
    lock_path = transition.state_path.with_name(f".{transition.state_path.name}.lock")

    result = run_transition(transition.state_path, transition.candidate_path)

    assert result.returncode == 2
    assert "revision" in result.stderr
    assert not lock_path.exists()


def test_transition_resolves_state_symlink_before_locking_and_writing(tmp_path: Path) -> None:
    transition = prepare_transition(tmp_path)
    alias = tmp_path / "state-alias.json"
    try:
        alias.symlink_to(transition.state_path)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symbolic links are unavailable: {error}")

    result = run_transition(alias, transition.candidate_path)

    assert result.returncode == 0, result.stderr
    assert alias.is_symlink()
    assert load_state(transition.state_path) == transition.candidate


def test_transition_rejects_state_symlink_loop(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    loop_path = tmp_path / "state-loop.json"
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text("{}", encoding="utf-8")
    try:
        state_path.symlink_to(loop_path.name)
        loop_path.symlink_to(state_path.name)
    except (NotImplementedError, OSError) as error:
        pytest.skip(f"symbolic links are unavailable: {error}")

    with pytest.raises(control_state.ControlStateError, match="cannot resolve state paths"):
        control_state.apply_completion_transition(state_path, candidate_path)


def test_git_rejects_non_utf8_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def invalid_utf8(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        del args, kwargs
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    monkeypatch.setattr(control_state.subprocess, "run", invalid_utf8)
    git_runner = control_state._git  # pyright: ignore[reportPrivateUsage]

    with pytest.raises(control_state.ControlStateError, match="valid UTF-8"):
        git_runner(tmp_path, "status")


def test_lock_close_failure_does_not_override_success(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    lock_path = state_path.with_name(f".{state_path.name}.lock")
    original_open = os.open
    original_close = os.close
    descriptor = original_open(lock_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)

    def return_descriptor(*args: object, **kwargs: object) -> int:
        del args, kwargs
        return descriptor

    def fail_close(candidate: int) -> None:
        assert candidate == descriptor
        original_close(candidate)
        raise OSError("close failed")

    monkeypatch.setattr(control_state.os, "open", return_descriptor)
    monkeypatch.setattr(control_state.os, "close", fail_close)
    transition_lock = control_state._state_transition_lock  # pyright: ignore[reportPrivateUsage]

    try:
        with (
            caplog.at_level(logging.WARNING, logger=control_state.__name__),
            transition_lock(state_path),
        ):
            pass
    finally:
        with suppress(OSError):
            original_close(descriptor)

    assert not lock_path.exists()
    assert "cannot close state transition lock" in caplog.text


def test_lock_unlink_failure_does_not_override_validation_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    state_path = tmp_path / "state.json"
    lock_path = state_path.with_name(f".{state_path.name}.lock")
    original_unlink = Path.unlink

    def fail_lock_unlink(path: Path, missing_ok: bool = False) -> None:
        if path == lock_path:
            raise OSError("unlink failed")
        original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_lock_unlink)
    transition_lock = control_state._state_transition_lock  # pyright: ignore[reportPrivateUsage]

    try:
        with (
            caplog.at_level(logging.WARNING, logger=control_state.__name__),
            pytest.raises(control_state.ControlStateError, match="validation failed"),
            transition_lock(state_path),
        ):
            raise control_state.ControlStateError("validation failed")
    finally:
        original_unlink(lock_path, missing_ok=True)

    assert "cannot remove state transition lock" in caplog.text


# --- Session activation (D-0010) and session-generic completion ---------------------------

SESSION_01_EVIDENCE_KEYS = (
    "playbook_steps_mapped",
    "architecture_and_adrs_complete",
    "state_event_job_enums_in_code",
    "typed_contracts_pass_validation",
    "configuration_encodes_playbook_defaults",
    "integration_strategy_explicit",
    "adversarial_review_resolved",
    "control_files_and_checkpoint_current",
    CLOSURE_EVIDENCE_KEY,
)


def activation_candidate(state: ControlState) -> ControlState:
    candidate = copy.deepcopy(state)
    candidate.update(
        {
            "state_revision": state["state_revision"] + 1,
            "session_status": "incomplete",
            "current_session": state["next_session"],
            "updated_at": "2026-08-10T00:00:00Z",
        }
    )
    candidate["required_completion_evidence"] = dict.fromkeys(SESSION_01_EVIDENCE_KEYS, False)
    return candidate


@dataclass(frozen=True)
class CompletedRepository:
    repo: Path
    state_path: Path
    candidate_path: Path


def prepare_completed_session_zero(tmp_path: Path) -> CompletedRepository:
    transition = prepare_transition(tmp_path)
    result = run_transition(transition.state_path, transition.candidate_path)
    assert result.returncode == 0, result.stderr
    git(transition.repo, "add", "docs/control/IMPLEMENTATION_STATE.json")
    git(transition.repo, "commit", "-m", "chore(control): complete session 00 bootstrap")
    candidate_path = tmp_path / "activation.json"
    write_state(candidate_path, activation_candidate(load_state(transition.state_path)))
    return CompletedRepository(transition.repo, transition.state_path, candidate_path)


def test_real_entrypoint_activates_the_recorded_next_session(tmp_path: Path) -> None:
    prepared = prepare_completed_session_zero(tmp_path)
    before = load_state(prepared.state_path)

    result = run_transition(prepared.state_path, prepared.candidate_path, "activate")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["applied"] is True
    assert payload["command"] == "activate"
    assert payload["session"] == 1
    after = load_state(prepared.state_path)
    assert after["current_session"] == 1
    assert after["session_status"] == "incomplete"
    assert after["completed_sessions"] == [0]
    assert after["next_session"] == 1
    assert after["next_prompt"] == control_state.SESSION_PROMPTS[1]
    assert after["state_revision"] == before["state_revision"] + 1
    assert after["head_sha"] == before["head_sha"]
    assert not any(after["required_completion_evidence"].values())
    assert not list(prepared.state_path.parent.glob(".IMPLEMENTATION_STATE.json.*.tmp"))


def test_activation_does_not_require_a_clean_worktree(tmp_path: Path) -> None:
    prepared = prepare_completed_session_zero(tmp_path)
    (prepared.repo / "evidence.txt").write_text("session 01 work in progress\n", encoding="utf-8")

    result = run_transition(prepared.state_path, prepared.candidate_path, "activate")

    assert result.returncode == 0, result.stderr


def activate_wrong_session(candidate: ControlState) -> None:
    candidate["current_session"] = 2


def activate_claiming_evidence(candidate: ControlState) -> None:
    candidate["required_completion_evidence"]["adversarial_review_resolved"] = True


def activate_without_closure_key(candidate: ControlState) -> None:
    del candidate["required_completion_evidence"][CLOSURE_EVIDENCE_KEY]


def activate_with_closure_key_only(candidate: ControlState) -> None:
    candidate["required_completion_evidence"] = {CLOSURE_EVIDENCE_KEY: False}


def activate_with_extra_key(candidate: ControlState) -> None:
    candidate["required_completion_evidence"][""] = False


def activate_rewriting_completed_sessions(candidate: ControlState) -> None:
    candidate["completed_sessions"] = []


def activate_advancing_next_session(candidate: ControlState) -> None:
    candidate["next_session"] = 2


def activate_rewriting_head(candidate: ControlState) -> None:
    candidate["head_sha"] = "f" * 40


def activate_as_complete(candidate: ControlState) -> None:
    candidate["session_status"] = "complete"


def activate_skipping_revision(candidate: ControlState) -> None:
    candidate["state_revision"] += 1


def activate_removing_blocker(candidate: ControlState) -> None:
    candidate["blockers"] = []


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (activate_wrong_session, "current_session must equal next_session"),
        (activate_claiming_evidence, "cannot claim any completion evidence"),
        (activate_without_closure_key, "exactly the session 01 completion evidence keys"),
        (activate_with_closure_key_only, "exactly the session 01 completion evidence keys"),
        (activate_with_extra_key, "exactly the session 01 completion evidence keys"),
        (activate_rewriting_completed_sessions, "completed_sessions cannot change"),
        (activate_advancing_next_session, "next_session cannot change"),
        (activate_rewriting_head, "head_sha cannot change"),
        (activate_as_complete, "activated session must be incomplete"),
        (activate_skipping_revision, "revision"),
        (activate_removing_blocker, "blockers cannot change"),
    ],
)
def test_real_entrypoint_rejects_invalid_activation_without_writing(
    tmp_path: Path,
    mutation: Mutation,
    expected: str,
) -> None:
    prepared = prepare_completed_session_zero(tmp_path)
    candidate = load_state(prepared.candidate_path)
    mutation(candidate)
    write_state(prepared.candidate_path, candidate)
    original = prepared.state_path.read_bytes()

    result = run_transition(prepared.state_path, prepared.candidate_path, "activate")

    assert result.returncode == 2
    assert expected in result.stderr
    assert prepared.state_path.read_bytes() == original


def test_double_activation_is_rejected(tmp_path: Path) -> None:
    prepared = prepare_completed_session_zero(tmp_path)
    assert run_transition(prepared.state_path, prepared.candidate_path, "activate").returncode == 0
    activated = load_state(prepared.state_path)
    again = copy.deepcopy(activated)
    again["state_revision"] += 1
    again["updated_at"] = "2026-08-11T00:00:00Z"
    write_state(prepared.candidate_path, again)
    original = prepared.state_path.read_bytes()

    result = run_transition(prepared.state_path, prepared.candidate_path, "activate")

    assert result.returncode == 2
    assert "must be complete before activation" in result.stderr
    assert prepared.state_path.read_bytes() == original


def test_completion_without_activation_is_rejected(tmp_path: Path) -> None:
    prepared = prepare_completed_session_zero(tmp_path)
    completed_zero = load_state(prepared.state_path)
    premature = copy.deepcopy(completed_zero)
    premature.update(
        {
            "state_revision": completed_zero["state_revision"] + 1,
            "completed_sessions": [0, 1],
            "current_session": 1,
            "next_session": 2,
            "next_prompt": control_state.SESSION_PROMPTS[2],
            "updated_at": "2026-08-11T00:00:00Z",
        }
    )
    write_state(prepared.candidate_path, premature)
    original = prepared.state_path.read_bytes()

    result = run_transition(prepared.state_path, prepared.candidate_path)

    assert result.returncode == 2
    assert "expected incomplete-to-complete" in result.stderr
    assert prepared.state_path.read_bytes() == original


def prepare_session_one_closure(tmp_path: Path) -> tuple[CompletedRepository, ControlState, str]:
    prepared = prepare_completed_session_zero(tmp_path)
    assert run_transition(prepared.state_path, prepared.candidate_path, "activate").returncode == 0
    activated = load_state(prepared.state_path)
    activated["required_completion_evidence"] = {
        key: key != CLOSURE_EVIDENCE_KEY for key in SESSION_01_EVIDENCE_KEYS
    }
    activated["updated_at"] = "2026-08-12T00:00:00Z"
    write_state(prepared.state_path, activated)
    git(prepared.repo, "add", "docs/control/IMPLEMENTATION_STATE.json")
    git(prepared.repo, "commit", "-m", "docs(architecture): define playbook automation contracts")
    closure = git(prepared.repo, "rev-parse", "HEAD")
    candidate = copy.deepcopy(activated)
    candidate.update(
        {
            "state_revision": activated["state_revision"] + 1,
            "session_status": "complete",
            "completed_sessions": [0, 1],
            "next_session": 2,
            "next_prompt": control_state.SESSION_PROMPTS[2],
            "evidence_closure_commit_sha": closure,
            "head_sha": closure,
            "updated_at": "2026-08-13T00:00:00Z",
        }
    )
    candidate["transition_contract"] = {
        **candidate["transition_contract"],
        "completion_requires_next_session": 2,
    }
    candidate["required_completion_evidence"] = dict.fromkeys(SESSION_01_EVIDENCE_KEYS, True)
    write_state(prepared.candidate_path, candidate)
    return prepared, candidate, closure


def test_session_one_completes_after_activation_with_a_new_closure_commit(tmp_path: Path) -> None:
    prepared, candidate, closure = prepare_session_one_closure(tmp_path)

    result = run_transition(prepared.state_path, prepared.candidate_path)

    assert result.returncode == 0, result.stderr
    after = load_state(prepared.state_path)
    assert after == candidate
    assert after["completed_sessions"] == [0, 1]
    assert after["next_session"] == 2
    assert after["head_sha"] == closure
    assert after["evidence_closure_commit_sha"] == closure


def test_session_two_to_three_activation_fails_closed_without_session_03_keys(
    tmp_path: Path,
) -> None:
    """Dedicated test: Session 2→3 activation requires exactly the Session 03 evidence keys."""
    # Prepare a completed Session 01 (which points to Session 02)
    prepared, session_one_state, closure = prepare_session_one_closure(tmp_path)
    assert run_transition(prepared.state_path, prepared.candidate_path).returncode == 0

    # Activate Session 02
    session_two_keys = {
        "fresh_bootstrap_path_documented",
        "database_schema_and_migrations_work",
        "seeds_are_idempotent",
        "runtime_containers_start",
        "ci_configuration_complete",
        "foundation_tests_pass",
        "control_files_and_checkpoint_current",
        CLOSURE_EVIDENCE_KEY,
    }
    activated_02 = load_state(prepared.state_path)
    assert activated_02["current_session"] == 2
    activated_02["required_completion_evidence"] = dict.fromkeys(session_two_keys, False)
    activated_02["updated_at"] = "2026-08-14T00:00:00Z"
    write_state(prepared.state_path, activated_02)
    git(prepared.repo, "add", "docs/control/IMPLEMENTATION_STATE.json")
    git(prepared.repo, "commit", "-m", "chore(control): activate session 02")

    # Mark Session 02 complete with all evidence satisfied
    activated_02["required_completion_evidence"] = {
        key: key != CLOSURE_EVIDENCE_KEY for key in session_two_keys
    }
    activated_02["updated_at"] = "2026-08-15T00:00:00Z"
    write_state(prepared.state_path, activated_02)
    git(prepared.repo, "add", "docs/control/IMPLEMENTATION_STATE.json")
    git(prepared.repo, "commit", "-m", "docs(foundation): complete database and runtime foundation")
    closure_02 = git(prepared.repo, "rev-parse", "HEAD")

    completed_02 = copy.deepcopy(activated_02)
    completed_02.update(
        {
            "state_revision": activated_02["state_revision"] + 1,
            "session_status": "complete",
            "completed_sessions": [0, 1, 2],
            "next_session": 3,
            "next_prompt": control_state.SESSION_PROMPTS[3],
            "evidence_closure_commit_sha": closure_02,
            "head_sha": closure_02,
            "updated_at": "2026-08-16T00:00:00Z",
        }
    )
    completed_02["required_completion_evidence"] = dict.fromkeys(session_two_keys, True)
    completed_02["transition_contract"] = {
        **completed_02["transition_contract"],
        "completion_requires_next_session": 3,
    }
    write_state(prepared.candidate_path, completed_02)
    assert run_transition(prepared.state_path, prepared.candidate_path).returncode == 0

    # Now attempt to activate Session 03 with WRONG keys (missing Session 03 keys)
    bad_activation = copy.deepcopy(load_state(prepared.state_path))
    bad_activation.update(
        {
            "state_revision": bad_activation["state_revision"] + 1,
            "session_status": "incomplete",
            "current_session": 3,
            "updated_at": "2026-08-17T00:00:00Z",
        }
    )
    # Use Session 02 keys instead of Session 03 keys (wrong!)
    bad_activation["required_completion_evidence"] = dict.fromkeys(session_two_keys, False)
    write_state(prepared.candidate_path, bad_activation)
    original = prepared.state_path.read_bytes()

    result = run_transition(prepared.state_path, prepared.candidate_path, "activate")

    # Prove activation fails closed without Session 03 keys
    assert result.returncode == 2
    assert "session 03 completion evidence keys" in result.stderr
    assert prepared.state_path.read_bytes() == original  # State file unchanged


def reuse_prior_closure(candidate: ControlState, previous: ControlState) -> None:
    candidate["evidence_closure_commit_sha"] = previous["evidence_closure_commit_sha"]
    candidate["head_sha"] = previous["head_sha"]


def add_blocker(candidate: ControlState, previous: ControlState) -> None:
    del previous
    candidate["blockers"].append({"code": "NEW", "scope": "x", "detail": "added at completion"})


def wrong_next_prompt(candidate: ControlState, previous: ControlState) -> None:
    del previous
    candidate["next_prompt"] = control_state.SESSION_PROMPTS[3]


def stale_next_session_contract(candidate: ControlState, previous: ControlState) -> None:
    del previous
    candidate["transition_contract"]["completion_requires_next_session"] = 1


def weakened_transition_contract(candidate: ControlState, previous: ControlState) -> None:
    del previous
    candidate["transition_contract"]["unsupported_completion_is_rejected"] = False


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        (reuse_prior_closure, "new evidence-closure commit"),
        (add_blocker, "only remove existing blockers"),
        (wrong_next_prompt, "canonical Session 02 prompt"),
        (stale_next_session_contract, "must equal the new next_session"),
        (weakened_transition_contract, "transition_contract cannot change"),
    ],
)
def test_session_one_completion_rejections_do_not_write(
    tmp_path: Path,
    mutation: Callable[[ControlState, ControlState], None],
    expected: str,
) -> None:
    prepared, candidate, _ = prepare_session_one_closure(tmp_path)
    mutation(candidate, load_state(prepared.state_path))
    write_state(prepared.candidate_path, candidate)
    original = prepared.state_path.read_bytes()

    result = run_transition(prepared.state_path, prepared.candidate_path)

    assert result.returncode == 2
    assert expected in result.stderr
    assert prepared.state_path.read_bytes() == original


# --- Filesystem identity of the canonical state path (D-0009) -----------------------------


def test_hard_linked_state_path_outside_the_control_directory_is_rejected(tmp_path: Path) -> None:
    prepared = prepare_completed_session_zero(tmp_path)
    alias = tmp_path / "IMPLEMENTATION_STATE.json"
    try:
        os.link(prepared.state_path, alias)
    except OSError as error:
        pytest.skip(f"hard links unavailable: {error}")
    original = prepared.state_path.read_bytes()

    result = run_transition(alias, prepared.candidate_path, "activate")

    assert result.returncode == 2
    assert "state path must be repo_root/docs/control" in result.stderr
    assert prepared.state_path.read_bytes() == original


def test_case_variant_repo_root_spelling_is_the_same_worktree(tmp_path: Path) -> None:
    prepared = prepare_completed_session_zero(tmp_path)
    variant = prepared.repo.with_name(prepared.repo.name.swapcase())
    if not (variant.exists() and os.path.samefile(variant, prepared.repo)):
        pytest.skip("filesystem is case-sensitive; case-variant identity cannot be exercised")
    candidate = load_state(prepared.candidate_path)
    candidate["repo_root"] = str(variant)
    state = load_state(prepared.state_path)
    state["repo_root"] = str(variant)
    write_state(prepared.state_path, state)
    write_state(prepared.candidate_path, candidate)

    result = run_transition(prepared.state_path, prepared.candidate_path, "activate")

    assert result.returncode == 0, result.stderr


def test_same_file_helper_uses_inode_identity_not_spelling(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)
    assert control_state.same_file(alias, target)
    assert not control_state.same_file(tmp_path / "missing", target)


def test_every_known_session_prompt_has_an_evidence_contract_in_order() -> None:
    """A session cannot be activated or completed without its own evidence keys (D-0010)."""
    contracts = control_state.SESSION_EVIDENCE_KEYS
    assert set(contracts) <= set(control_state.SESSION_PROMPTS)
    assert sorted(contracts) == list(range(len(contracts))), "evidence contracts must be contiguous"
    for session, keys in contracts.items():
        assert CLOSURE_EVIDENCE_KEY in keys, session
        assert len(keys) >= 2, session
    assert set(contracts[0]) == set(SESSION_00_EVIDENCE_KEYS)
    assert set(contracts[1]) == set(SESSION_01_EVIDENCE_KEYS)
    assert set(contracts[2]) == {
        "fresh_bootstrap_path_documented",
        "database_schema_and_migrations_work",
        "seeds_are_idempotent",
        "runtime_containers_start",
        "ci_configuration_complete",
        "foundation_tests_pass",
        "control_files_and_checkpoint_current",
        CLOSURE_EVIDENCE_KEY,
    }
    assert set(contracts[3]) == {
        "orchestration_state_machine_implemented",
        "lease_and_worker_claiming_implemented",
        "retry_and_reconciliation_implemented",
        "event_driven_successors_transactional",
        "scheduler_timers_durable",
        "worker_scheduler_fail_closed",
        "concurrency_recovery_tests_pass",
        "control_files_and_checkpoint_current",
        CLOSURE_EVIDENCE_KEY,
    }
