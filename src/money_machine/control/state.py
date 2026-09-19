"""Validation and atomic persistence for implementation-state transitions."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tempfile
from collections.abc import Callable, Generator, Mapping
from contextlib import contextmanager, suppress
from pathlib import Path
from types import MappingProxyType
from typing import TypedDict, cast

SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
BOOTSTRAP_COMMIT_SUBJECT = "chore(bootstrap): initialise money machine autonomous monorepo"
CANONICAL_STATE_RELATIVE_PATH = Path("docs/control/IMPLEMENTATION_STATE.json")
SESSION_PROMPTS: Mapping[int, str] = MappingProxyType(
    {
        0: "03_SESSION_00_DISCOVERY_AND_REPO_BOOTSTRAP.md",
        1: "04_SESSION_01_PLAYBOOK_MAPPING_AND_ARCHITECTURE.md",
        2: "05_SESSION_02_ENGINEERING_FOUNDATION_AND_DATABASE.md",
        3: "06_SESSION_03_DURABLE_ORCHESTRATOR.md",
        4: "07_SESSION_04_AGENT_RUNTIME_AND_ROSTER.md",
        5: "08_SESSION_05_MARKET_RESEARCH_TO_PRODUCT_SPEC.md",
        6: "09_SESSION_06_NOTION_INTEGRATION_FOUNDATION.md",
        7: "10_SESSION_07_PRODUCT_BUILD_VARIANTS_AND_QA.md",
        8: "11_SESSION_08_MERCHANDISING_AND_ASSET_FACTORY.md",
        9: "12_SESSION_09_ETSY_DRAFT_PUBLISH_AND_PREFLIGHT.md",
        10: "13_SESSION_10_ANALYTICS_CULL_MULTIPLY_CLOSED_LOOP.md",
        11: "14_SESSION_11_CUSTOMER_SUPPORT_AND_REPAIR.md",
        12: "15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md",
        13: "16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md",
        14: "17_SESSION_14_DEPLOYMENT.md",
        15: "18_SESSION_15_LIVE_COMMISSIONING_AND_HANDOVER.md",
    }
)
SESSION_01_PROMPT = SESSION_PROMPTS[1]
SESSION_EVIDENCE_KEYS: Mapping[int, frozenset[str]] = MappingProxyType(
    {
        0: frozenset(
            {
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
                "evidence_closure_commit_recorded",
            }
        ),
        2: frozenset(
            {
                "fresh_bootstrap_path_documented",
                "database_schema_and_migrations_work",
                "seeds_are_idempotent",
                "runtime_containers_start",
                "ci_configuration_complete",
                "foundation_tests_pass",
                "control_files_and_checkpoint_current",
                "evidence_closure_commit_recorded",
            }
        ),
        1: frozenset(
            {
                "playbook_steps_mapped",
                "architecture_and_adrs_complete",
                "state_event_job_enums_in_code",
                "typed_contracts_pass_validation",
                "configuration_encodes_playbook_defaults",
                "integration_strategy_explicit",
                "adversarial_review_resolved",
                "control_files_and_checkpoint_current",
                "evidence_closure_commit_recorded",
            }
        ),
        3: frozenset(
            {
                # Session 03: orchestration primitives with deterministic fake handlers.
                # Worker/scheduler stay fail-closed (exit 78); live commissioning is Session 04.
                # "lease_and_worker_claiming_implemented" = library/test claim primitives under
                # test (FOR UPDATE SKIP LOCKED, heartbeat, expiry, lease recovery, concurrency
                # tests), NOT production worker claiming or exit-78 removal.
                "orchestration_state_machine_implemented",
                "lease_and_worker_claiming_implemented",
                "retry_and_reconciliation_implemented",
                "event_driven_successors_transactional",
                "scheduler_timers_durable",
                "worker_scheduler_fail_closed",
                "concurrency_recovery_tests_pass",
                "control_files_and_checkpoint_current",
                "evidence_closure_commit_recorded",
            }
        ),
        4: frozenset(
            {
                # Session 04: agent runtime, prompt registry, and complete roster.
                # Worker/scheduler STAY fail-closed (exit 78); Exit 78 removal requires decision
                # record + commissioning evidence gate (post-Session-04).
                # A01/A02 promoted to TESTED; A03-A16 registered at DESIGNED with contract tests
                # proving uncommissioned agents refuse production execution.
                "provider_abstraction_implemented",
                "prompt_registry_and_hashes_implemented",
                "agent_runner_integrated_with_jobs",
                "sixteen_agents_registered",
                "uncommissioned_agents_documented",
                "contract_and_runtime_tests_pass",
                "control_files_and_checkpoint_current",
                "evidence_closure_commit_recorded",
            }
        ),
    }
)
"""Each session's completion-evidence contract (D-0010). A session without an entry cannot be
activated or completed; adding a session means adding its keys here with its prompt."""
_NEXT_SESSION_CONTRACT_KEY = "completion_requires_next_session"
GIT_TIMEOUT_SECONDS = 30
LOGGER = logging.getLogger(__name__)


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
_ACTIVATION_MUTABLE_FIELDS = frozenset(
    {
        "state_revision",
        "session_status",
        "current_session",
        "updated_at",
        "required_completion_evidence",
    }
)
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
        "transition_contract",
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


def _require_same_fields(
    previous: ControlState,
    current: ControlState,
    mutable_fields: frozenset[str],
    label: str,
) -> None:
    previous_fields = set(previous)
    current_fields = set(current)
    if current_fields != previous_fields:
        raise ControlStateError(f"unsupported {label}: state fields cannot be added or removed")
    for field in sorted(previous_fields.difference(mutable_fields)):
        if previous[field] != current[field]:
            raise ControlStateError(f"unsupported {label}: {field} cannot change")


def validate_activation_transition(previous: ControlState, current: ControlState) -> None:
    """Validate the atomic activation of the recorded next session (D-0010).

    Activation preserves ``completed_sessions`` and the next-session pointer, moves
    ``current_session`` to ``next_session``, marks the session ``incomplete``, and installs
    the new session's own (all-false) completion evidence keys.
    """
    if previous["session_status"] != "complete":
        raise ControlStateError(
            "unsupported activation: the previous session must be complete before activation"
        )
    next_session = previous["next_session"]
    if next_session is None:
        raise ControlStateError("unsupported activation: no next session is recorded")
    if next_session not in SESSION_PROMPTS:
        raise ControlStateError(f"unsupported activation: no canonical prompt for {next_session}")
    if next_session != previous["current_session"] + 1:
        raise ControlStateError("unsupported activation: next_session must follow current_session")
    if current["current_session"] != next_session:
        raise ControlStateError("unsupported activation: current_session must equal next_session")
    if current["session_status"] != "incomplete":
        raise ControlStateError("unsupported activation: activated session must be incomplete")
    _require_same_fields(previous, current, _ACTIVATION_MUTABLE_FIELDS, "activation")
    if current["state_revision"] != previous["state_revision"] + 1:
        raise ControlStateError("state revision must advance exactly once")
    if current["updated_at"] == previous["updated_at"]:
        raise ControlStateError("updated_at must change for the activation transition")
    if previous["completed_sessions"] != list(range(next_session)):
        raise ControlStateError("previous completed_sessions are not contiguous")
    if previous["next_prompt"] != SESSION_PROMPTS[next_session]:
        raise ControlStateError("recorded next_prompt does not identify the canonical prompt")

    if next_session not in SESSION_EVIDENCE_KEYS:
        raise ControlStateError(
            f"unsupported activation: no completion evidence contract for session {next_session}"
        )
    evidence = current["required_completion_evidence"]
    if evidence.keys() != SESSION_EVIDENCE_KEYS[next_session]:
        raise ControlStateError(
            f"activation must install exactly the session {next_session:02d} completion "
            "evidence keys"
        )
    if any(evidence.values()):
        raise ControlStateError("activation cannot claim any completion evidence")


def validate_completion_transition(previous: ControlState, current: ControlState) -> None:
    """Validate the completion of the active session and the advance to the next one."""
    session = previous["current_session"]
    if session not in SESSION_PROMPTS or session + 1 not in SESSION_PROMPTS:
        raise ControlStateError(
            f"unsupported completion: no canonical prompt after session {session}"
        )
    if previous["session_status"] != "incomplete" or current["session_status"] != "complete":
        raise ControlStateError("unsupported completion: expected incomplete-to-complete")
    for field in _IDENTITY_FIELDS:
        if previous[field] != current[field]:
            raise ControlStateError(f"unsupported completion: {field} cannot change")

    _require_same_fields(previous, current, _COMPLETION_MUTABLE_FIELDS, "completion")

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
    if current["next_prompt"] != SESSION_PROMPTS[session + 1]:
        raise ControlStateError(
            f"next prompt must identify the canonical Session {session + 1:02d} prompt"
        )
    if current["updated_at"] == previous["updated_at"]:
        raise ControlStateError("updated_at must change for the completion transition")

    previous_contract = dict(previous["transition_contract"])
    current_contract = dict(current["transition_contract"])
    previous_contract.pop(_NEXT_SESSION_CONTRACT_KEY, None)
    current_contract.pop(_NEXT_SESSION_CONTRACT_KEY, None)
    if previous_contract != current_contract:
        raise ControlStateError("unsupported completion: transition_contract cannot change")
    if (
        _NEXT_SESSION_CONTRACT_KEY in previous["transition_contract"]
        and current["transition_contract"].get(_NEXT_SESSION_CONTRACT_KEY)
        != current["next_session"]
    ):
        raise ControlStateError(
            f"transition_contract.{_NEXT_SESSION_CONTRACT_KEY} must equal the new next_session"
        )

    previous_evidence = previous["required_completion_evidence"]
    current_evidence = current["required_completion_evidence"]
    if session not in SESSION_EVIDENCE_KEYS:
        raise ControlStateError(
            f"unsupported completion: no completion evidence contract for session {session}"
        )
    if (
        previous_evidence.keys() != SESSION_EVIDENCE_KEYS[session]
        or current_evidence.keys() != previous_evidence.keys()
    ):
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
    if session == 0:
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
    else:
        retained = [blocker for blocker in previous_blockers if blocker in current["blockers"]]
        if current["blockers"] != retained:
            raise ControlStateError(
                "completion may only remove existing blockers, never add or edit"
            )

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
    if not SHA_PATTERN.fullmatch(closure or ""):
        raise ControlStateError("evidence_closure_commit_sha must be a lowercase 40-character hash")
    if session == 0:
        if previous["head_sha"] != bootstrap:
            raise ControlStateError("pre-transition head_sha must identify the bootstrap commit")
        if previous["evidence_closure_commit_sha"] is not None:
            raise ControlStateError("pre-transition evidence_closure_commit_sha must be null")
    else:
        previous_closure = previous["evidence_closure_commit_sha"]
        if not SHA_PATTERN.fullmatch(previous_closure or ""):
            raise ControlStateError(
                "pre-transition evidence_closure_commit_sha must identify the prior closure commit"
            )
        if previous["head_sha"] != previous_closure:
            raise ControlStateError(
                "pre-transition head_sha must identify the prior closure commit"
            )
        if closure == previous_closure:
            raise ControlStateError("each session requires a new evidence-closure commit")
    if bootstrap == closure:
        raise ControlStateError("bootstrap and evidence-closure commit SHAs must be distinct")
    if current["head_sha"] != closure:
        raise ControlStateError("head_sha must identify the pre-transition evidence-closure commit")


def _git(
    repo_root: Path,
    *arguments: str,
    allowed_returncodes: frozenset[int] = frozenset({0}),
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise ControlStateError(
            f"Git command timed out after {GIT_TIMEOUT_SECONDS} seconds"
        ) from error
    except UnicodeError as error:
        raise ControlStateError("Git output is not valid UTF-8") from error
    except OSError as error:
        raise ControlStateError(f"cannot execute Git: {error}") from error
    if result.returncode not in allowed_returncodes:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise ControlStateError(f"Git verification failed for {' '.join(arguments)}: {detail}")
    return result


def _resolve_commit(repo_root: Path, commit_id: str, label: str) -> str:
    result = _git(repo_root, "rev-parse", "--verify", f"{commit_id}^{{commit}}")
    resolved = result.stdout.strip()
    if resolved != commit_id:
        raise ControlStateError(f"{label} must be a full commit object ID")
    return resolved


def _assert_repo_at_closure(
    repo_root: Path,
    closure: str,
    recorded_branch: str,
) -> None:
    head = _git(repo_root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    if head != closure:
        raise ControlStateError("repository HEAD must equal the evidence-closure commit")
    branch = _git(repo_root, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    if branch != recorded_branch:
        raise ControlStateError("repository HEAD must be attached to the recorded branch")
    status = _git(
        repo_root,
        "status",
        "--porcelain=v1",
        "--untracked-files=no",
    ).stdout
    if status:
        raise ControlStateError("all tracked repository files must be clean before transition")


def same_file(left: Path, right: Path) -> bool:
    """Compare filesystem identity (D-0009); spelling differences on one inode are equal."""
    try:
        return os.path.samefile(left, right)
    except OSError:
        return False


def _validate_repo_identity(state_path: Path, current: ControlState) -> tuple[Path, str]:
    """Prove the state file is the canonical file inside the recorded Git worktree root."""
    repo_root = Path(current["repo_root"])
    if not repo_root.is_dir():
        raise ControlStateError("repo_root must identify an existing Git repository")
    expected_state_path = repo_root / CANONICAL_STATE_RELATIVE_PATH
    # The directory entry must be the canonical one: same parent directory inode and exact
    # file name. A hard link elsewhere shares the inode but would leave the canonical entry
    # unchanged after an atomic replace, so it is rejected.
    if (
        state_path.name != expected_state_path.name
        or not same_file(state_path.parent, expected_state_path.parent)
        or not same_file(state_path, expected_state_path)
    ):
        raise ControlStateError(
            "state path must be repo_root/docs/control/IMPLEMENTATION_STATE.json"
        )
    git_root = Path(_git(repo_root, "rev-parse", "--show-toplevel").stdout.strip())
    if not same_file(git_root, repo_root):
        raise ControlStateError("repo_root must identify the Git worktree root")
    recorded_branch = current["branch"]
    actual_branch = _git(repo_root, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    if actual_branch != recorded_branch:
        raise ControlStateError("recorded branch must equal the current Git branch")
    return repo_root, recorded_branch


def _validate_git_evidence(
    state_path: Path,
    previous: ControlState,
    current: ControlState,
) -> tuple[Path, str]:
    repo_root, recorded_branch = _validate_repo_identity(state_path, current)

    bootstrap = current["bootstrap_commit_sha"]
    closure = current["evidence_closure_commit_sha"]
    if bootstrap is None or closure is None:
        raise ControlStateError("both commit SHAs are required")
    _resolve_commit(repo_root, bootstrap, "bootstrap_commit_sha")
    _resolve_commit(repo_root, closure, "evidence_closure_commit_sha")

    bootstrap_subject = _git(repo_root, "show", "-s", "--format=%s", bootstrap).stdout.rstrip("\n")
    if bootstrap_subject != BOOTSTRAP_COMMIT_SUBJECT:
        raise ControlStateError(
            f"bootstrap commit subject must be exactly {BOOTSTRAP_COMMIT_SUBJECT!r}"
        )
    ancestry_base = bootstrap if previous["current_session"] == 0 else previous["head_sha"]
    if ancestry_base is None:
        raise ControlStateError("pre-transition head_sha is required for ancestry verification")
    _resolve_commit(repo_root, ancestry_base, "pre-transition head_sha")
    ancestry = _git(
        repo_root,
        "merge-base",
        "--is-ancestor",
        ancestry_base,
        closure,
        allowed_returncodes=frozenset({0, 1}),
    )
    if ancestry.returncode != 0:
        raise ControlStateError(
            "the prior closure (or bootstrap) commit must be an ancestor of the new closure commit"
        )

    state_relative = CANONICAL_STATE_RELATIVE_PATH
    _assert_repo_at_closure(repo_root, closure, recorded_branch)
    closure_document = _git(
        repo_root,
        "show",
        f"{closure}:{state_relative.as_posix()}",
    ).stdout
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
            with suppress(OSError):
                os.close(descriptor)
            raise
        with stream:
            if path.exists() and hasattr(os, "fchmod"):
                os.fchmod(stream.fileno(), path.stat().st_mode)
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


@contextmanager
def _state_transition_lock(state_path: Path) -> Generator[None]:
    lock_path = state_path.with_name(f".{state_path.name}.lock")
    try:
        descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except OSError as error:
        raise ControlStateError(f"cannot acquire state transition lock: {error}") from error
    try:
        yield
    finally:
        try:
            os.close(descriptor)
        except OSError as error:
            LOGGER.warning("cannot close state transition lock: %s", error)
        try:
            lock_path.unlink()
        except OSError as error:
            LOGGER.warning("cannot remove state transition lock: %s", error)


def _resolve_transition_paths(state_path: Path, candidate_path: Path) -> tuple[Path, Path]:
    try:
        state_path = state_path.resolve(strict=True)
        candidate_path = candidate_path.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise ControlStateError(f"cannot resolve state paths: {error}") from error
    if same_file(state_path, candidate_path):
        raise ControlStateError("candidate must be separate from the current state file")
    return state_path, candidate_path


def _apply_transition(
    state_path: Path,
    candidate_path: Path,
    validate: Callable[[ControlState, ControlState], None],
    verify_repository: Callable[[Path, ControlState, ControlState], None],
) -> ControlState:
    state_path, candidate_path = _resolve_transition_paths(state_path, candidate_path)
    with _state_transition_lock(state_path):
        previous, _ = _parse_state(state_path, "current state")
        current, current_raw = _parse_state(candidate_path, "candidate state")
        validate(previous, current)
        verify_repository(state_path, previous, current)
        try:
            _atomic_write_json(state_path, current_raw)
        except OSError as error:
            raise ControlStateError(f"atomic state write failed: {error}") from error
        return current


def _verify_completion_repository(
    state_path: Path,
    previous: ControlState,
    current: ControlState,
) -> None:
    repo_root, closure = _validate_git_evidence(state_path, previous, current)
    _assert_repo_at_closure(repo_root, closure, current["branch"])


def _verify_activation_repository(
    state_path: Path,
    previous: ControlState,
    current: ControlState,
) -> None:
    del previous
    _validate_repo_identity(state_path, current)


def apply_completion_transition(state_path: Path, candidate_path: Path) -> ControlState:
    """Validate a completion candidate and atomically replace the current state file."""
    return _apply_transition(
        state_path,
        candidate_path,
        validate_completion_transition,
        _verify_completion_repository,
    )


def apply_activation_transition(state_path: Path, candidate_path: Path) -> ControlState:
    """Validate an activation candidate and atomically replace the current state file.

    Activation does not require a clean worktree: it is the first recorded act of a session
    and is itself checkpointed by a later commit.
    """
    return _apply_transition(
        state_path,
        candidate_path,
        validate_activation_transition,
        _verify_activation_repository,
    )
