"""Validation and atomic persistence for implementation-state completion."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import TypedDict, cast

from money_machine.control.locking import ControlLockError, exclusive_control_lock

SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
SUPPORTED_COMPLETION_SESSION = 0
BOOTSTRAP_COMMIT_SUBJECT = "chore(bootstrap): initialise money machine autonomous monorepo"
CANONICAL_STATE_RELATIVE_PATH = Path("docs/control/IMPLEMENTATION_STATE.json")
SESSION_01_PROMPT = "04_SESSION_01_PLAYBOOK_MAPPING_AND_ARCHITECTURE.md"
CONTROL_GIT_TIMEOUT_SECONDS = 10.0


class ControlState(TypedDict):
    """Fields required by the Session 00 completion contract."""

    programme: str
    version: str
    repo_root: str
    windows_repo_root: str
    branch: str
    head_sha: str | None
    bootstrap_commit_sha: str | None
    evidence_closure_commit_sha: str | None
    last_verified_commit: str | None
    state_revision: int
    session_status: str
    current_session: int
    completed_sessions: list[int]
    services: dict[str, str]
    commissioned_agents: list[str]
    tests: dict[str, str]
    environment_versions: dict[str, str]
    blockers: list[Blocker]
    next_session: int | None
    next_prompt: str
    required_completion_evidence: dict[str, bool]
    transition_contract: dict[str, bool | int]
    updated_at: str


class Blocker(TypedDict):
    """A typed fail-closed reason recorded in continuity state."""

    code: str
    scope: str
    detail: str


class ControlStateError(ValueError):
    """Raised when state cannot be read or a transition is unsafe."""


_REQUIRED_FIELDS = frozenset(ControlState.__required_keys__)
_IDENTITY_FIELDS = ("programme", "version", "repo_root", "branch", "current_session")
_CLOSURE_EVIDENCE_KEY = "evidence_closure_commit_recorded"
_OUTER_GATES_BLOCKER = "SESSION_00_OUTER_GATES_PENDING"
_COMPLETION_MUTABLE_FIELDS = frozenset(
    {
        "state_revision",
        "session_status",
        "completed_sessions",
        "next_session",
        "next_prompt",
        "head_sha",
        "evidence_closure_commit_sha",
        "updated_at",
        "required_completion_evidence",
        "blockers",
    }
)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_string(state: dict[str, object], field: str, *, nullable: bool = False) -> None:
    value = state[field]
    if isinstance(value, str) or (nullable and value is None):
        return
    raise ControlStateError(f"{field} must be {'a string or null' if nullable else 'a string'}")


def _parse_state(path: Path, label: str) -> tuple[ControlState, dict[str, object]]:
    try:
        decoded = cast(object, json.loads(path.read_text(encoding="utf-8")))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ControlStateError(f"cannot read {label}: {error}") from error
    if not isinstance(decoded, dict):
        raise ControlStateError(f"{label} must be a JSON object with string keys")
    untyped = cast(dict[object, object], decoded)
    if not all(isinstance(key, str) for key in untyped):
        raise ControlStateError(f"{label} must be a JSON object with string keys")

    raw = cast(dict[str, object], untyped)
    missing = _REQUIRED_FIELDS.difference(raw)
    if missing:
        raise ControlStateError(f"{label} is missing required fields: {', '.join(sorted(missing))}")

    for field in (
        "programme",
        "version",
        "repo_root",
        "windows_repo_root",
        "branch",
        "session_status",
        "next_prompt",
        "updated_at",
    ):
        _require_string(raw, field)
    for field in (
        "head_sha",
        "bootstrap_commit_sha",
        "evidence_closure_commit_sha",
        "last_verified_commit",
    ):
        _require_string(raw, field, nullable=True)
    for field in ("state_revision", "current_session"):
        if not _is_int(raw[field]):
            raise ControlStateError(f"{field} must be an integer")
    if raw["next_session"] is not None and not _is_int(raw["next_session"]):
        raise ControlStateError("next_session must be an integer or null")

    completed = raw["completed_sessions"]
    if not isinstance(completed, list):
        raise ControlStateError("completed_sessions must be a list of integers")
    untyped_completed = cast(list[object], completed)
    if not all(_is_int(item) for item in untyped_completed):
        raise ControlStateError("completed_sessions must be a list of integers")
    evidence = raw["required_completion_evidence"]
    if not isinstance(evidence, dict):
        raise ControlStateError("required_completion_evidence must map string keys to booleans")
    untyped_evidence = cast(dict[object, object], evidence)
    if not all(isinstance(key, str) for key in untyped_evidence) or not all(
        isinstance(value, bool) for value in untyped_evidence.values()
    ):
        raise ControlStateError("required_completion_evidence must map string keys to booleans")

    for field in ("services", "tests", "environment_versions"):
        value = raw[field]
        if not isinstance(value, dict):
            raise ControlStateError(f"{field} must map string keys to string values")
        mapping = cast(dict[object, object], value)
        if not all(isinstance(key, str) for key in mapping) or not all(
            isinstance(item, str) for item in mapping.values()
        ):
            raise ControlStateError(f"{field} must map string keys to string values")

    commissioned_agents = raw["commissioned_agents"]
    if not isinstance(commissioned_agents, list) or not all(
        isinstance(agent, str) for agent in cast(list[object], commissioned_agents)
    ):
        raise ControlStateError("commissioned_agents must be a list of strings")

    blockers = raw["blockers"]
    if not isinstance(blockers, list):
        raise ControlStateError("blockers must be a list of code/scope/detail objects")
    for blocker in cast(list[object], blockers):
        if not isinstance(blocker, dict):
            raise ControlStateError("blockers must be a list of code/scope/detail objects")
        blocker_mapping = cast(dict[object, object], blocker)
        if blocker_mapping.keys() != {"code", "scope", "detail"} or not all(
            isinstance(item, str) for item in blocker_mapping.values()
        ):
            raise ControlStateError("blockers must be a list of code/scope/detail objects")

    transition_contract = raw["transition_contract"]
    if not isinstance(transition_contract, dict):
        raise ControlStateError("transition_contract must map strings to booleans or integers")
    transition_mapping = cast(dict[object, object], transition_contract)
    if not all(isinstance(key, str) for key in transition_mapping) or not all(
        isinstance(item, (bool, int)) for item in transition_mapping.values()
    ):
        raise ControlStateError("transition_contract must map strings to booleans or integers")

    return cast(ControlState, raw), raw


def validate_completion_transition(previous: ControlState, current: ControlState) -> None:
    """Validate the only currently supported completion transition: Session 00."""
    if previous["current_session"] != SUPPORTED_COMPLETION_SESSION:
        raise ControlStateError("unsupported completion: only Session 00 is currently supported")
    if previous["session_status"] != "incomplete" or current["session_status"] != "complete":
        raise ControlStateError("unsupported completion: expected incomplete-to-complete")
    for field in _IDENTITY_FIELDS:
        if previous[field] != current[field]:
            raise ControlStateError(f"unsupported completion: {field} cannot change")

    previous_fields = set(previous)
    current_fields = set(current)
    if current_fields != previous_fields:
        raise ControlStateError("unsupported completion: state fields cannot be added or removed")
    for field in sorted(previous_fields.difference(_COMPLETION_MUTABLE_FIELDS)):
        if previous[field] != current[field]:
            raise ControlStateError(f"unsupported completion: {field} cannot change")

    if current["state_revision"] != previous["state_revision"] + 1:
        raise ControlStateError("state revision must advance exactly once")

    expected_previous_sessions = list(range(previous["current_session"]))
    expected_completed_sessions = [*expected_previous_sessions, previous["current_session"]]
    if previous["completed_sessions"] != expected_previous_sessions:
        raise ControlStateError("previous completed_sessions are not contiguous")
    if current["completed_sessions"] != expected_completed_sessions:
        raise ControlStateError("completed_sessions must append the current session exactly once")
    if current["next_session"] != current["current_session"] + 1:
        raise ControlStateError("next session must advance exactly once")
    if current["next_prompt"] != SESSION_01_PROMPT:
        raise ControlStateError("next prompt must identify the canonical Session 01 prompt")
    if current["updated_at"] == previous["updated_at"]:
        raise ControlStateError("updated_at must change for the completion transition")

    previous_evidence = previous["required_completion_evidence"]
    current_evidence = current["required_completion_evidence"]
    if not previous_evidence or current_evidence.keys() != previous_evidence.keys():
        raise ControlStateError("completion evidence keys are missing or unsupported")
    missing_previous_evidence = sorted(key for key, value in previous_evidence.items() if not value)
    if missing_previous_evidence != [_CLOSURE_EVIDENCE_KEY]:
        raise ControlStateError(
            "pre-transition evidence must be complete except for the evidence-closure commit"
        )
    for key, value in previous_evidence.items():
        expected = True if key == _CLOSURE_EVIDENCE_KEY else value
        if current_evidence[key] != expected:
            raise ControlStateError(
                "completion evidence cannot change except for the evidence-closure commit"
            )
    missing_evidence = sorted(key for key, value in current_evidence.items() if not value)
    if missing_evidence:
        raise ControlStateError(f"completion evidence is incomplete: {', '.join(missing_evidence)}")

    previous_blockers = previous["blockers"]
    outer_gate_blockers = [
        blocker for blocker in previous_blockers if blocker["code"] == _OUTER_GATES_BLOCKER
    ]
    if len(outer_gate_blockers) != 1:
        raise ControlStateError(
            "pre-transition blockers must contain exactly one Session 00 outer-gates blocker"
        )
    expected_blockers = [
        blocker for blocker in previous_blockers if blocker["code"] != _OUTER_GATES_BLOCKER
    ]
    if current["blockers"] != expected_blockers:
        raise ControlStateError("completion may remove only the Session 00 outer-gates blocker")

    bootstrap = previous["bootstrap_commit_sha"]
    closure = current["evidence_closure_commit_sha"]
    if not SHA_PATTERN.fullmatch(bootstrap or ""):
        raise ControlStateError(
            "pre-transition bootstrap_commit_sha must be a lowercase 40-character hash"
        )
    if previous["last_verified_commit"] != bootstrap:
        raise ControlStateError(
            "pre-transition last_verified_commit must identify the bootstrap commit"
        )
    if previous["head_sha"] != bootstrap:
        raise ControlStateError("pre-transition head_sha must identify the bootstrap commit")
    if previous["evidence_closure_commit_sha"] is not None:
        raise ControlStateError("pre-transition evidence_closure_commit_sha must be null")
    if not SHA_PATTERN.fullmatch(closure or ""):
        raise ControlStateError("evidence_closure_commit_sha must be a lowercase 40-character hash")
    if bootstrap == closure:
        raise ControlStateError("bootstrap and evidence-closure commit SHAs must be distinct")
    if current["head_sha"] != closure:
        raise ControlStateError("head_sha must identify the pre-transition evidence-closure commit")


def _run_git(repo_root: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ("git", *arguments),
            cwd=repo_root,
            timeout=CONTROL_GIT_TIMEOUT_SECONDS,
            text=True,
            encoding="utf-8",
            capture_output=True,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise ControlStateError("git command timed out") from error
    except OSError as error:
        raise ControlStateError(f"cannot execute Git: {error}") from error
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise ControlStateError(f"Git verification failed for {' '.join(arguments)}: {detail}")
    return result.stdout


def _resolve_commit(repo_root: Path, commit_id: str, label: str) -> str:
    resolved = _run_git(repo_root, "rev-parse", "--verify", f"{commit_id}^{{commit}}").strip()
    if resolved != commit_id:
        raise ControlStateError(f"{label} must be a full commit object ID")
    return resolved


def _assert_repo_at_closure(
    repo_root: Path,
    closure: str,
    recorded_branch: str,
) -> None:
    head = _run_git(repo_root, "rev-parse", "--verify", "HEAD^{commit}").strip()
    if head != closure:
        raise ControlStateError("repository HEAD must equal the evidence-closure commit")
    branch = _run_git(repo_root, "symbolic-ref", "--quiet", "--short", "HEAD").strip()
    if branch != recorded_branch:
        raise ControlStateError("repository HEAD must be attached to the recorded branch")
    status = _run_git(
        repo_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=no",
    )
    if status:
        raise ControlStateError("all tracked repository files must be clean before transition")


def _validate_git_evidence(
    state_path: Path,
    previous: ControlState,
    current: ControlState,
) -> tuple[Path, str]:
    repo_root = Path(current["repo_root"]).resolve()
    expected_state_path = (repo_root / CANONICAL_STATE_RELATIVE_PATH).resolve()
    if state_path.resolve() != expected_state_path:
        raise ControlStateError(
            "state path must be repo_root/docs/control/IMPLEMENTATION_STATE.json"
        )
    if not repo_root.is_dir():
        raise ControlStateError("repo_root must identify an existing Git repository")

    git_root = Path(_run_git(repo_root, "rev-parse", "--show-toplevel").strip()).resolve()
    if git_root != repo_root:
        raise ControlStateError("repo_root must identify the Git worktree root")
    recorded_branch = current["branch"]
    actual_branch = _run_git(repo_root, "symbolic-ref", "--quiet", "--short", "HEAD").strip()
    if actual_branch != recorded_branch:
        raise ControlStateError("recorded branch must equal the current Git branch")

    bootstrap = current["bootstrap_commit_sha"]
    closure = current["evidence_closure_commit_sha"]
    if bootstrap is None or closure is None:
        raise ControlStateError("both commit SHAs are required")
    _resolve_commit(repo_root, bootstrap, "bootstrap_commit_sha")
    _resolve_commit(repo_root, closure, "evidence_closure_commit_sha")

    bootstrap_subject = _run_git(repo_root, "show", "-s", "--format=%s", bootstrap).rstrip("\n")
    if bootstrap_subject != BOOTSTRAP_COMMIT_SUBJECT:
        raise ControlStateError(
            f"bootstrap commit subject must be exactly {BOOTSTRAP_COMMIT_SUBJECT!r}"
        )
    ancestry = _run_git(
        repo_root,
        "rev-list",
        "--ancestry-path",
        f"{bootstrap}..{closure}",
    )
    if not ancestry.strip():
        raise ControlStateError("bootstrap commit must be an ancestor of evidence-closure commit")

    state_relative = CANONICAL_STATE_RELATIVE_PATH
    _assert_repo_at_closure(repo_root, closure, recorded_branch)
    closure_document = _run_git(
        repo_root,
        "show",
        f"{closure}:{state_relative.as_posix()}",
    )
    try:
        decoded_closure = cast(object, json.loads(closure_document))
    except json.JSONDecodeError as error:
        raise ControlStateError(
            "evidence-closure commit contains invalid implementation state"
        ) from error
    if not isinstance(decoded_closure, dict):
        raise ControlStateError("evidence-closure commit contains invalid implementation state")
    closure_state = cast(dict[object, object], decoded_closure)
    if (
        closure_state.get("head_sha") == closure
        or closure_state.get("evidence_closure_commit_sha") == closure
    ):
        raise ControlStateError("evidence-closure commit must not claim its own object ID")
    if closure_state != cast(dict[object, object], previous):
        raise ControlStateError(
            "evidence-closure commit must contain the exact pre-transition state"
        )
    return repo_root, closure


def _atomic_write_json(path: Path, document: dict[str, object]) -> None:
    payload = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temporary_path = Path(temporary_name)
    try:
        try:
            stream = os.fdopen(descriptor, "wb")
        except BaseException:
            os.close(descriptor)
            raise
        with stream:
            fchmod = getattr(os, "fchmod", None)
            if path.exists() and fchmod is not None:
                fchmod(stream.fileno(), path.stat().st_mode)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
        if hasattr(os, "O_DIRECTORY"):
            directory_descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def apply_completion_transition(state_path: Path, candidate_path: Path) -> ControlState:
    """Validate a candidate and atomically replace the current state file."""
    try:
        canonical_state_path = state_path.resolve()
        canonical_candidate_path = candidate_path.resolve()
        if canonical_state_path == canonical_candidate_path:
            raise ControlStateError("candidate must be separate from the current state file")
    except OSError as error:
        raise ControlStateError(f"cannot resolve state paths: {error}") from error

    try:
        lock_path = canonical_state_path.with_name(f"{canonical_state_path.name}.lock")
        with exclusive_control_lock(lock_path):
            previous, _ = _parse_state(canonical_state_path, "current state")
            current, current_raw = _parse_state(canonical_candidate_path, "candidate state")
            validate_completion_transition(previous, current)
            repo_root, closure = _validate_git_evidence(canonical_state_path, previous, current)
            _assert_repo_at_closure(repo_root, closure, current["branch"])
            try:
                _atomic_write_json(canonical_state_path, current_raw)
            except OSError as error:
                raise ControlStateError(f"atomic state write failed: {error}") from error
            return current
    except ControlLockError as error:
        raise ControlStateError(f"control lock failed: {error}") from error
