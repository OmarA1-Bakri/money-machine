"""Session 07 evidence record, closure, revoke, and history replay.

Q4 (closure re-alignment) and Q7 (revoke-only rollback) are implemented as
specified and stay unmerged until Omar's G0 covers both. These commands never
read an anchor from the environment, argv, or config.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import NoReturn, cast

import yaml

from money_machine.cli.notion_sandbox_guard import SANDBOX_PARENT_PAGE_ID, SANDBOX_SPACE_ID
from money_machine.control.state import (
    CANONICAL_STATE_RELATIVE_PATH,
    GIT_TIMEOUT_SECONDS,
    SESSION_EVIDENCE_KEYS,
    SHA_PATTERN,
    ControlState,
    ControlStateError,
    _apply_transition,  # pyright: ignore[reportPrivateUsage]
    _assert_repo_at_closure,  # pyright: ignore[reportPrivateUsage]
    _git,  # pyright: ignore[reportPrivateUsage]
    _is_int,  # pyright: ignore[reportPrivateUsage]
    _resolve_commit,  # pyright: ignore[reportPrivateUsage]
    _validate_repo_identity,  # pyright: ignore[reportPrivateUsage]
    validate_activation_transition,
)

REPLAY_ANCHOR_SHA = "00b952a83bffcec8d442468223d64dd9b2d3e6df"
S07_CLOSE_TIP = "b782751fdb1b255c436ff7f6fa655e6d783b1e8c"
S06_PRIOR_WAVE_TIP = "0f94d585f23d79e5ac18479f01e14f67cbaad332"
CLOSURE_KEY = "evidence_closure_commit_recorded"
LABEL_RECORD = "record-evidence"
LABEL_CLOSURE = "record-closure"
LABEL_REVOKE = "revoke-evidence"
REPLAY_REFUSED = "replay refused:"
SHALLOW_REPLAY = "replay refused: repository is shallow"
ANCHOR_UNRESOLVED = "replay refused: anchor does not resolve"
ANCHOR_NOT_ANCESTOR = "replay refused: anchor is not a first-parent ancestor of HEAD"
FIXTURE_MISMATCH = "replay refused: anchor state does not match the rev-64 fixture"
WORKTREE_MISMATCH = "replay refused: working tree state does not match HEAD"
SQUASH_REQUIRED = "replay refused: state must be squash-merged"
BAD_WINDOW = "replay refused: bad window-end"
NO_WINDOW = "replay refused: no window end"
INVALID_STEP = "replay refused: invalid step"
CITATION_REQUIRED = "session 07 true evidence keys must be cited"
PRE_CLOSURE_PINS = "session 07 pre-closure commits are not pinned"
CLOSURE_CITATION_PINS = "session 07 closure commits must equal the closure citation"
CLOSURE_NAMES_ITSELF = "evidence-closure commit must not claim its own object ID"
CLOSURE_STATE_MISMATCH = "evidence-closure commit must contain the exact pre-transition state"

_RFC3339_Z = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RECORD_CITATION_FIELDS = frozenset(
    {"pr", "merge_commit", "manifest", "manifest_blob_sha256", "ci_run", "recorded_at"}
)
_CLOSURE_CITATION_FIELDS = frozenset({"closure_commit", "recorded_at", "g7_record_blob_sha256"})
_REVOKE_ENTRY_FIELDS = frozenset({"key", "reason", "revoked_at", "revoked_in_rev"})
_MANIFEST_FIELDS = frozenset(
    {"session", "key", "phase", "artifacts", "reviewer_pass", "verifier_pass", "go_record_sha256"}
)
_ARTIFACT_FIELDS = frozenset({"kind", "path", "sha256"})
_G7_FIELDS = frozenset({"agents", "state", "g7_go_record_sha256", "approved_at"})
_G7_AGENTS = ("A07", "A08", "A09")
_G7_PATH = "docs/evidence/s07/commissioning/g7-record.json"
_AGENTS_PATH = "config/agents.yaml"
_NARRATIVE_CONTROL_FILES = (
    "docs/control/IMPLEMENTATION_LOG.md",
    "docs/control/NEXT_SESSION.md",
    "docs/control/TEST_EVIDENCE.md",
    "docs/control/DECISIONS.md",
)
_RUN_EVIDENCE_KINDS = frozenset({"p2_build_exec", "p3_variants_exec", "p4_qa", "p4_repair_rerun"})
_RECORD_MUTABLE = frozenset(
    {
        "state_revision",
        "updated_at",
        "required_completion_evidence",
        "evidence_citations",
    }
)
_CLOSURE_MUTABLE = _RECORD_MUTABLE | {"head_sha", "evidence_closure_commit_sha"}
_FIXTURE_PATH = Path(__file__).resolve().parents[3] / "tests/fixtures/control/state_rev64.json"
_STATE_RELATIVE = CANONICAL_STATE_RELATIVE_PATH.as_posix()

NON_CLOSURE_KEYS: tuple[str, ...] = (
    "notion_product_builder_implemented",
    "shared_databases_built",
    "home_dashboard_built",
    "notification_dashboard_built",
    "identity_hubs_built",
    "variant_builder_implemented",
    "product_qa_implemented",
    "product_fact_ledger_persisted",
    "build_workflow_linked",
    "product_build_tests_pass",
    "control_files_and_checkpoint_current",
)
_KEYS_BEFORE_CONTROL = frozenset(NON_CLOSURE_KEYS[:-1])
S07_EVIDENCE_KINDS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "notion_product_builder_implemented": frozenset({"p2_build_exec", "p4_qa"}),
        "shared_databases_built": frozenset({"p2_build_exec", "p4_qa"}),
        "home_dashboard_built": frozenset({"p2_build_exec", "p4_qa"}),
        "notification_dashboard_built": frozenset({"p2_build_exec", "p4_qa"}),
        "identity_hubs_built": frozenset({"p2_build_exec", "p4_qa"}),
        "variant_builder_implemented": frozenset({"p3_variants_exec", "p4_qa"}),
        "product_qa_implemented": frozenset({"p4_qa", "p4_repair_rerun"}),
        "product_fact_ledger_persisted": frozenset({"p5_ledger"}),
        "build_workflow_linked": frozenset({"p6_test_record"}),
        "product_build_tests_pass": frozenset({"p8a_ci_record"}),
        "control_files_and_checkpoint_current": frozenset({"p8b_control_record"}),
    }
)


def _raw(state: ControlState) -> dict[str, object]:
    return cast(dict[str, object], state)


def _evidence(state: ControlState) -> dict[str, object]:
    evidence = _raw(state).get("required_completion_evidence")
    if not isinstance(evidence, dict):
        raise ControlStateError("required_completion_evidence must map string keys to booleans")
    return cast(dict[str, object], evidence)


def _reject(label: str, detail: str) -> NoReturn:
    raise ControlStateError(f"unsupported {label}: {detail}")


def _git_bytes(
    repo_root: Path,
    *arguments: str,
    allowed_returncodes: frozenset[int] = frozenset({0}),
) -> subprocess.CompletedProcess[bytes]:
    """Run git and return the raw stdout bytes. Evidence hashes use those bytes."""
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), *arguments],
            check=False,
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise ControlStateError(
            f"Git command timed out after {GIT_TIMEOUT_SECONDS} seconds"
        ) from error
    except OSError as error:
        raise ControlStateError(f"cannot execute Git: {error}") from error
    if result.returncode not in allowed_returncodes:
        detail = result.stderr.decode("utf-8", errors="replace").strip() or "unknown Git error"
        raise ControlStateError(f"Git verification failed for {' '.join(arguments)}: {detail}")
    return result


def _require_session_seven_contract(previous: ControlState, label: str) -> None:
    if previous["session_status"] != "complete":
        _reject(label, "the session must be complete")
    session = previous["current_session"]
    if session not in SESSION_EVIDENCE_KEYS:
        _reject(label, f"no completion evidence contract for session {session}")
    if session != 7:
        _reject(label, "only session 07 evidence can be recorded")


def _require_mutable_fields(
    previous: ControlState,
    current: ControlState,
    mutable: frozenset[str],
    label: str,
) -> None:
    previous_fields = set(_raw(previous))
    current_fields = set(_raw(current))
    added = current_fields - previous_fields
    removed = previous_fields - current_fields
    if removed == {"evidence_citations"} and not added:
        _reject(label, "evidence_citations cannot be removed")
    if removed or not added <= {"evidence_citations"}:
        _reject(label, "state fields cannot be added or removed")
    if "evidence_citations" in added and "evidence_citations" in previous_fields:
        _reject(label, "evidence_citations cannot be created a second time")
    for field in sorted(previous_fields - mutable):
        if _raw(previous)[field] != _raw(current)[field]:
            _reject(label, f"{field} cannot change")


def _require_revision_and_timestamp(
    previous: ControlState, current: ControlState, label: str
) -> None:
    if (
        not _is_int(current["state_revision"])
        or current["state_revision"] != previous["state_revision"] + 1
    ):
        raise ControlStateError("state revision must advance exactly once")
    if current["updated_at"] == previous["updated_at"]:
        _reject(label, "updated_at must change")


def _require_evidence_shape(state: ControlState, label: str) -> dict[str, bool]:
    evidence = _evidence(state)
    if set(evidence) != set(SESSION_EVIDENCE_KEYS[7]):
        _reject(label, "evidence keys must equal the session 07 contract")
    typed: dict[str, bool] = {}
    for key, value in evidence.items():
        if not isinstance(value, bool):
            _reject(label, "evidence values must be booleans")
        typed[key] = value
    return typed


def _as_object(value: object, label: str, detail: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _reject(label, detail)
    return cast(dict[str, object], value)


def _citation_block(state: ControlState, label: str, *, required: bool) -> dict[str, object] | None:
    raw = _raw(state).get("evidence_citations", None)
    if raw is None:
        if required:
            _reject(label, "evidence_citations is required")
        return None
    return _as_object(raw, label, "evidence_citations must be an object")


def _session_citation_map(block: dict[str, object], label: str) -> dict[str, object]:
    keys = set(block)
    if keys not in ({"7"}, {"7", "7_revoked"}):
        _reject(label, "evidence_citations keys must be 7 or 7 and 7_revoked")
    return _as_object(block["7"], label, "session 07 citations must be an object")


def _require_same_revoked(
    previous: dict[str, object] | None, current: dict[str, object], label: str
) -> None:
    previous_keys = set() if previous is None else set(previous)
    if "7_revoked" in current and "7_revoked" not in previous_keys:
        _reject(label, "7_revoked cannot be created by this command")
    if (
        previous is not None
        and "7_revoked" in previous
        and current.get("7_revoked") != previous.get("7_revoked")
    ):
        _reject(label, "7_revoked must stay byte-identical")


def _require_record_citation(citation: object, key: str) -> None:
    body = _as_object(citation, LABEL_RECORD, f"citation for {key} must be an object")
    if set(body) != set(_RECORD_CITATION_FIELDS):
        _reject(LABEL_RECORD, f"citation for {key} has the wrong fields")
    pr = body["pr"]
    merge = body["merge_commit"]
    manifest = body["manifest"]
    digest = body["manifest_blob_sha256"]
    recorded_at = body["recorded_at"]
    if not isinstance(pr, int) or isinstance(pr, bool) or pr <= 0:
        _reject(LABEL_RECORD, f"citation for {key} needs a positive pull request number")
    if not isinstance(merge, str) or SHA_PATTERN.fullmatch(merge) is None:
        _reject(LABEL_RECORD, f"citation for {key} needs a 40-character merge commit")
    expected_manifest = f"docs/evidence/s07/{key}/manifest.json"
    if manifest != expected_manifest:
        _reject(LABEL_RECORD, f"citation for {key} must name {expected_manifest}")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        _reject(LABEL_RECORD, f"citation for {key} needs a sha256 manifest digest")
    if not isinstance(body["ci_run"], str):
        _reject(LABEL_RECORD, f"citation for {key} needs a string ci_run")
    if not isinstance(recorded_at, str) or _RFC3339_Z.fullmatch(recorded_at) is None:
        _reject(LABEL_RECORD, f"citation for {key} needs an RFC3339 Z timestamp")


def _align_citations(
    previous_map: Mapping[str, object],
    current_map: Mapping[str, object],
    previous_evidence: Mapping[str, bool],
    current_evidence: Mapping[str, bool],
    flipped: set[str],
) -> None:
    for key in set(current_map) | set(previous_map):
        if key not in SESSION_EVIDENCE_KEYS[7]:
            _reject(LABEL_RECORD, f"citation names a key outside session 07: {key}")
    for key in SESSION_EVIDENCE_KEYS[7]:
        cited = key in current_map
        if current_evidence[key] is True and not cited:
            _reject(LABEL_RECORD, f"{key} is true without a citation")
        if current_evidence[key] is False and cited:
            _reject(LABEL_RECORD, f"{key} is false but cited")
        if key in flipped:
            _require_record_citation(current_map[key], key)
        elif current_evidence[key] is True and current_map[key] != previous_map.get(key):
            _reject(LABEL_RECORD, "existing evidence citation cannot change")
        elif previous_evidence[key] is True and key not in previous_map:
            _reject(LABEL_RECORD, f"existing true key {key} was not cited")


def validate_record_evidence_transition(previous: ControlState, current: ControlState) -> None:
    """Structural rules for ``record-evidence``. Manifest bytes are checked at apply time."""
    _require_session_seven_contract(previous, LABEL_RECORD)
    _require_mutable_fields(previous, current, _RECORD_MUTABLE, LABEL_RECORD)
    _require_revision_and_timestamp(previous, current, LABEL_RECORD)
    previous_evidence = _require_evidence_shape(previous, LABEL_RECORD)
    current_evidence = _require_evidence_shape(current, LABEL_RECORD)
    flipped: set[str] = set()
    for key in (*NON_CLOSURE_KEYS, CLOSURE_KEY):
        before = previous_evidence[key]
        after = current_evidence[key]
        if before is False and after is True:
            if key == CLOSURE_KEY:
                _reject(LABEL_RECORD, "the closure key cannot be recorded by record-evidence")
            flipped.add(key)
        elif before is True and after is False:
            _reject(LABEL_RECORD, "evidence cannot change from true to false")
        elif before != after:
            _reject(LABEL_RECORD, "evidence values must be booleans")
    if not flipped:
        _reject(LABEL_RECORD, "at least one false evidence key must become true")
    if "control_files_and_checkpoint_current" in flipped and any(
        previous_evidence[key] is not True for key in _KEYS_BEFORE_CONTROL
    ):
        _reject(LABEL_RECORD, "keys 1-10 must already be true before the control-file key")
    previous_block = _citation_block(previous, LABEL_RECORD, required=False)
    current_block = _citation_block(current, LABEL_RECORD, required=True)
    assert current_block is not None
    current_map = _session_citation_map(current_block, LABEL_RECORD)
    if previous_block is None:
        if set(current_block) != {"7"}:
            _reject(LABEL_RECORD, "the first record may create only the session 07 citation map")
    else:
        if set(current_block) != set(previous_block):
            _reject(LABEL_RECORD, "evidence_citations keys cannot be added or removed")
        _require_same_revoked(previous_block, current_block, LABEL_RECORD)
    previous_map = (
        {} if previous_block is None else _session_citation_map(previous_block, LABEL_RECORD)
    )
    _align_citations(previous_map, current_map, previous_evidence, current_evidence, flipped)


def _require_closure_citation(citation: object, commit: str) -> None:
    body = _as_object(citation, LABEL_CLOSURE, "closure citation must be an object")
    if set(body) != set(_CLOSURE_CITATION_FIELDS):
        _reject(LABEL_CLOSURE, "closure citation has the wrong fields")
    if body["closure_commit"] != commit or SHA_PATTERN.fullmatch(commit) is None:
        _reject(LABEL_CLOSURE, "closure citation must name the new closure commit")
    recorded_at = body["recorded_at"]
    digest = body["g7_record_blob_sha256"]
    if not isinstance(recorded_at, str) or _RFC3339_Z.fullmatch(recorded_at) is None:
        _reject(LABEL_CLOSURE, "closure citation needs an RFC3339 Z timestamp")
    if not isinstance(digest, str) or _SHA256.fullmatch(digest) is None:
        _reject(LABEL_CLOSURE, "closure citation needs the g7-record sha256")


def validate_record_closure_transition(previous: ControlState, current: ControlState) -> None:
    """Structural rules for ``record-closure``. History checks run at apply time."""
    _require_session_seven_contract(previous, LABEL_CLOSURE)
    if (
        previous["head_sha"] != S07_CLOSE_TIP
        or previous["evidence_closure_commit_sha"] != S06_PRIOR_WAVE_TIP
    ):
        _reject(LABEL_CLOSURE, "pre-transition commits are not the session 07 close pins")
    previous_evidence = _require_evidence_shape(previous, LABEL_CLOSURE)
    current_evidence = _require_evidence_shape(current, LABEL_CLOSURE)
    if previous_evidence[CLOSURE_KEY] is True:
        _reject(LABEL_CLOSURE, "closure is already recorded")
    if any(
        previous_evidence[key] is not True or current_evidence[key] is not True
        for key in NON_CLOSURE_KEYS
    ):
        _reject(LABEL_CLOSURE, "all eleven non-closure keys must be true")
    if current_evidence[CLOSURE_KEY] is not True:
        _reject(LABEL_CLOSURE, "the closure key must become true")
    _require_mutable_fields(previous, current, _CLOSURE_MUTABLE, LABEL_CLOSURE)
    _require_revision_and_timestamp(previous, current, LABEL_CLOSURE)
    head = current["head_sha"]
    closure = current["evidence_closure_commit_sha"]
    if not isinstance(head, str) or not isinstance(closure, str):
        _reject(LABEL_CLOSURE, "both commit fields must be full commit ids")
    if head == S06_PRIOR_WAVE_TIP:
        _reject(LABEL_CLOSURE, "head_sha cannot be the prior-wave closure")
    if closure == S07_CLOSE_TIP:
        _reject(LABEL_CLOSURE, "evidence_closure_commit_sha cannot be the session 07 close tip")
    old_pins = {S06_PRIOR_WAVE_TIP, S07_CLOSE_TIP}
    if head in old_pins or closure in old_pins:
        _reject(LABEL_CLOSURE, "closure commit is not a new commit")
    if head != closure or SHA_PATTERN.fullmatch(head) is None:
        _reject(
            LABEL_CLOSURE,
            "head_sha and evidence_closure_commit_sha must both equal the closure commit",
        )
    previous_block = _citation_block(previous, LABEL_CLOSURE, required=True)
    current_block = _citation_block(current, LABEL_CLOSURE, required=True)
    assert previous_block is not None and current_block is not None
    if set(current_block) != set(previous_block):
        _reject(LABEL_CLOSURE, "evidence_citations keys cannot be added or removed")
    _require_same_revoked(previous_block, current_block, LABEL_CLOSURE)
    previous_map = _session_citation_map(previous_block, LABEL_CLOSURE)
    current_map = _session_citation_map(current_block, LABEL_CLOSURE)
    for key in NON_CLOSURE_KEYS:
        if (
            key not in previous_map
            or key not in current_map
            or previous_map[key] != current_map[key]
        ):
            _reject(LABEL_CLOSURE, f"{key} must stay cited and unchanged")
        _require_record_citation(current_map[key], key)
    if CLOSURE_KEY in previous_map:
        _reject(LABEL_CLOSURE, "the closure key must not already be cited")
    _require_closure_citation(current_map.get(CLOSURE_KEY), head)


def _revoked_entries(block: dict[str, object] | None) -> list[object]:
    if block is None or "7_revoked" not in block:
        return []
    entries = block["7_revoked"]
    if not isinstance(entries, list):
        _reject(LABEL_REVOKE, "7_revoked must be a list")
    return cast(list[object], entries)


def validate_revoke_evidence_transition(previous: ControlState, current: ControlState) -> None:
    """Structural rules for ``revoke-evidence``. Remaining manifests are rechecked at apply time."""
    _require_session_seven_contract(previous, LABEL_REVOKE)
    _require_mutable_fields(previous, current, _RECORD_MUTABLE, LABEL_REVOKE)
    _require_revision_and_timestamp(previous, current, LABEL_REVOKE)
    previous_evidence = _require_evidence_shape(previous, LABEL_REVOKE)
    current_evidence = _require_evidence_shape(current, LABEL_REVOKE)
    if previous_evidence[CLOSURE_KEY] is True or current_evidence[CLOSURE_KEY] is True:
        _reject(LABEL_REVOKE, "revoke is refused once the closure key is true")
    revoked = [
        key
        for key in NON_CLOSURE_KEYS
        if previous_evidence[key] is True and current_evidence[key] is False
    ]
    for key in (*NON_CLOSURE_KEYS, CLOSURE_KEY):
        before = previous_evidence[key]
        after = current_evidence[key]
        if before is False and after is True:
            _reject(LABEL_REVOKE, "revoke cannot mark an evidence key true")
        if before != after and not (before is True and after is False):
            _reject(LABEL_REVOKE, "evidence values must be booleans")
    if not revoked:
        _reject(LABEL_REVOKE, "at least one cited evidence key must become false")
    previous_block = _citation_block(previous, LABEL_REVOKE, required=True)
    current_block = _citation_block(current, LABEL_REVOKE, required=True)
    assert previous_block is not None and current_block is not None
    if "7" not in current_block or "7_revoked" not in current_block:
        _reject(LABEL_REVOKE, "revoke must keep session 07 citations and append 7_revoked")
    if set(current_block) != {"7", "7_revoked"}:
        _reject(LABEL_REVOKE, "evidence_citations keys must be 7 and 7_revoked")
    previous_map = _session_citation_map(previous_block, LABEL_REVOKE)
    current_map = _session_citation_map(current_block, LABEL_REVOKE)
    for key in revoked:
        if key not in previous_map:
            _reject(LABEL_REVOKE, f"{key} is not cited")
    for key in SESSION_EVIDENCE_KEYS[7]:
        if current_evidence[key] is True and current_map.get(key) != previous_map.get(key):
            _reject(LABEL_REVOKE, "citations for keys that stay true cannot change")
        if current_evidence[key] is False and key in current_map:
            _reject(LABEL_REVOKE, f"revoked key {key} must not stay cited")
    previous_entries = _revoked_entries(previous_block)
    current_entries = _revoked_entries(current_block)
    if current_entries[: len(previous_entries)] != previous_entries:
        _reject(LABEL_REVOKE, "7_revoked is append-only")
    appended = current_entries[len(previous_entries) :]
    appended_keys = [
        _as_object(item, LABEL_REVOKE, "revoke entry must be an object").get("key")
        for item in appended
    ]
    if appended_keys != revoked:
        _reject(LABEL_REVOKE, "new 7_revoked entries must follow the revoked keys in order")
    for item in appended:
        body = _as_object(item, LABEL_REVOKE, "revoke entry must be an object")
        if set(body) != set(_REVOKE_ENTRY_FIELDS):
            _reject(LABEL_REVOKE, "revoke entry has the wrong fields")
        reason = body["reason"]
        revoked_at = body["revoked_at"]
        if not isinstance(reason, str) or reason == "":
            _reject(LABEL_REVOKE, "reason must be non-empty")
        if not isinstance(revoked_at, str) or _RFC3339_Z.fullmatch(revoked_at) is None:
            _reject(LABEL_REVOKE, "revoked_at must be RFC3339 Z")
        if body["revoked_in_rev"] != current["state_revision"]:
            _reject(LABEL_REVOKE, "revoked_in_rev must equal the new state revision")


def _blob_bytes(repo_root: Path, commit: str, path: str) -> bytes:
    try:
        return _git_bytes(repo_root, "cat-file", "blob", f"{commit}:{path}").stdout
    except ControlStateError as error:
        raise ControlStateError(f"evidence blob missing at {commit}:{path}") from error


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _is_ancestor(repo_root: Path, ancestor: str, descendant: str) -> bool:
    if ancestor == descendant:
        return True
    result = _git(
        repo_root,
        "merge-base",
        "--is-ancestor",
        ancestor,
        descendant,
        allowed_returncodes=frozenset({0, 1}),
    )
    return result.returncode == 0


def _load_json_blob(repo_root: Path, commit: str, path: str, label: str) -> dict[str, object]:
    try:
        decoded = cast(object, json.loads(_blob_bytes(repo_root, commit, path).decode("utf-8")))
    except (UnicodeError, json.JSONDecodeError):
        _reject(label, f"{path} at {commit} is not JSON")
    return _as_object(decoded, label, f"{path} at {commit} must be an object")


def _artifact_path_ok(key: str, path: object) -> bool:
    if not isinstance(path, str) or path.startswith("/") or ".." in path.split("/"):
        return False
    prefix = f"docs/evidence/s07/{key}/"
    if not path.startswith(prefix) or path == prefix:
        return False
    return Path(path).name != "README.md"


def _check_run_evidence(kind: str, document: Mapping[str, object], label: str) -> None:
    if kind not in _RUN_EVIDENCE_KINDS:
        return
    if document.get("mode") != "execute":
        _reject(label, f"{kind} mode must be execute")
    if document.get("redaction_self_check") != "PASS":
        _reject(label, f"{kind} redaction_self_check must be PASS")
    if document.get("space_id") != SANDBOX_SPACE_ID:
        _reject(label, f"{kind} space_id must be the sandbox space")
    parent = document.get("parent_page_id", document.get("parent"))
    if parent != SANDBOX_PARENT_PAGE_ID:
        _reject(label, f"{kind} parent must be the sandbox parent")
    if kind == "p4_qa" and document.get("qa_verdict") != "PASS":
        _reject(label, "p4_qa qa_verdict must be PASS")


def _check_kind_payload(
    repo_root: Path,
    commit: str,
    key: str,
    kind: str,
    document: Mapping[str, object],
    citations: Mapping[str, object],
) -> None:
    _check_run_evidence(kind, document, LABEL_RECORD)
    if kind == "p5_ledger":
        qa_citation = citations.get("product_qa_implemented")
        qa_body = _as_object(qa_citation, LABEL_RECORD, "product qa must already be cited")
        qa_merge = qa_body["merge_commit"]
        if not isinstance(qa_merge, str):
            _reject(LABEL_RECORD, "product qa citation is unusable")
        qa_manifest = _load_manifest(repo_root, qa_merge, "product_qa_implemented")
        expected = next(
            (
                artifact["sha256"]
                for artifact in cast(list[dict[str, object]], qa_manifest["artifacts"])
                if artifact.get("kind") == "p4_qa"
            ),
            None,
        )
        if document.get("qa_record_sha256") != expected:
            _reject(LABEL_RECORD, "p5_ledger qa_record_sha256 must equal the cited p4_qa")
    if kind == "p6_test_record":
        nodes = document.get("test_node_ids")
        if (
            not isinstance(nodes, list)
            or not nodes
            or not all(isinstance(node, str) and node for node in nodes)
            or not isinstance(document.get("ci_run"), str)
            or document.get("ci_run") == ""
        ):
            _reject(LABEL_RECORD, "p6_test_record needs test node ids and a ci run")
    if kind == "p8a_ci_record" and (
        not isinstance(document.get("ci_run"), str) or document.get("ci_run") == ""
    ):
        _reject(LABEL_RECORD, "p8a_ci_record needs a ci run")
    if kind == "p8b_control_record":
        recorded = document.get("control_file_sha256")
        if not isinstance(recorded, dict):
            _reject(LABEL_RECORD, "p8b_control_record needs control file digests")
        digests = cast(dict[object, object], recorded)
        if set(digests) != set(_NARRATIVE_CONTROL_FILES):
            _reject(LABEL_RECORD, "p8b_control_record must name the four narrative control files")
        for path in _NARRATIVE_CONTROL_FILES:
            if digests[path] != _sha256(_blob_bytes(repo_root, commit, path)):
                _reject(LABEL_RECORD, f"p8b_control_record digest does not match {path}")


def _load_manifest(repo_root: Path, commit: str, key: str) -> dict[str, object]:
    path = f"docs/evidence/s07/{key}/manifest.json"
    manifest = _load_json_blob(repo_root, commit, path, LABEL_RECORD)
    if set(manifest) != set(_MANIFEST_FIELDS):
        _reject(LABEL_RECORD, f"manifest for {key} has the wrong fields")
    if manifest.get("session") != 7 or manifest.get("key") != key:
        _reject(LABEL_RECORD, f"manifest for {key} must declare session 7 and that key")
    if not isinstance(manifest.get("phase"), str):
        _reject(LABEL_RECORD, f"manifest for {key} needs a phase string")
    reviewer_pass = manifest.get("reviewer_pass")
    verifier_pass = manifest.get("verifier_pass")
    if not isinstance(reviewer_pass, str) or not isinstance(verifier_pass, str):
        _reject(LABEL_RECORD, f"manifest for {key} needs reviewer and verifier pass strings")
    go_record = manifest.get("go_record_sha256")
    if go_record is not None and (
        not isinstance(go_record, str) or _SHA256.fullmatch(go_record) is None
    ):
        _reject(LABEL_RECORD, f"manifest for {key} has a bad go_record_sha256")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        _reject(LABEL_RECORD, f"manifest for {key} needs an artifact list")
    return manifest


def verify_record_evidence_git(
    repo_root: Path,
    current: ControlState,
    *,
    head_commit: str,
) -> None:
    """Re-check every true non-closure citation against blobs at its merge commit."""
    block = _citation_block(current, LABEL_RECORD, required=True)
    assert block is not None
    current_map = _session_citation_map(block, LABEL_RECORD)
    evidence = _require_evidence_shape(current, LABEL_RECORD)
    for key in NON_CLOSURE_KEYS:
        if evidence[key] is not True:
            continue
        citation = _as_object(
            current_map[key], LABEL_RECORD, f"citation for {key} must be an object"
        )
        _check_one_citation(repo_root, citation, key, head_commit, current_map)


def _check_one_citation(
    repo_root: Path,
    citation: Mapping[str, object],
    key: str,
    head_commit: str,
    citations: Mapping[str, object],
) -> None:
    merge = citation["merge_commit"]
    if not isinstance(merge, str):
        _reject(LABEL_RECORD, f"citation for {key} needs a merge commit")
    _resolve_commit(repo_root, merge, f"merge_commit for {key}")
    if not _is_ancestor(repo_root, S07_CLOSE_TIP, merge):
        _reject(LABEL_RECORD, f"merge_commit for {key} must descend from the session 07 close tip")
    if not _is_ancestor(repo_root, merge, head_commit):
        _reject(LABEL_RECORD, f"merge_commit for {key} must be an ancestor of the recorded commit")
    manifest_path = f"docs/evidence/s07/{key}/manifest.json"
    if _sha256(_blob_bytes(repo_root, merge, manifest_path)) != citation["manifest_blob_sha256"]:
        _reject(LABEL_RECORD, f"manifest blob sha256 for {key} does not match the citation")
    manifest = _load_manifest(repo_root, merge, key)
    artifacts = cast(list[object], manifest["artifacts"])
    kinds: list[str] = []
    payloads: list[dict[str, object]] = []
    for artifact in artifacts:
        body = _as_object(artifact, LABEL_RECORD, f"artifact for {key} must be an object")
        if set(body) != set(_ARTIFACT_FIELDS):
            _reject(LABEL_RECORD, f"artifact for {key} has the wrong fields")
        kind = body["kind"]
        path = body["path"]
        recorded = body["sha256"]
        if not isinstance(kind, str) or not _artifact_path_ok(key, path):
            _reject(LABEL_RECORD, f"artifact path or kind for {key} is not allowed")
        if not isinstance(recorded, str) or _SHA256.fullmatch(recorded) is None:
            _reject(LABEL_RECORD, f"artifact for {key} needs a sha256")
        assert isinstance(path, str)
        if _sha256(_blob_bytes(repo_root, merge, path)) != recorded:
            _reject(LABEL_RECORD, f"artifact blob sha256 for {key} does not match the manifest")
        payloads.append(_load_json_blob(repo_root, merge, path, LABEL_RECORD))
        kinds.append(kind)
    if len(kinds) != len(set(kinds)) or set(kinds) != set(S07_EVIDENCE_KINDS[key]):
        _reject(LABEL_RECORD, f"artifact kinds for {key} must equal the frozen set")
    for kind, payload in zip(kinds, payloads, strict=True):
        _check_kind_payload(repo_root, merge, key, kind, payload, citations)


def _state_document_at(repo_root: Path, commit: str) -> dict[str, object]:
    try:
        decoded = cast(
            object,
            json.loads(_blob_bytes(repo_root, commit, _STATE_RELATIVE).decode("utf-8")),
        )
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ControlStateError(
            "evidence-closure commit contains invalid implementation state"
        ) from error
    return _as_object(
        decoded, LABEL_CLOSURE, "evidence-closure commit contains invalid implementation state"
    )


def _check_g7(repo_root: Path, commit: str, citation: Mapping[str, object]) -> None:
    payload = _blob_bytes(repo_root, commit, _G7_PATH)
    if _sha256(payload) != citation["g7_record_blob_sha256"]:
        _reject(LABEL_CLOSURE, "g7-record blob sha256 does not match the closure citation")
    try:
        document = _as_object(
            json.loads(payload.decode("utf-8")), LABEL_CLOSURE, "g7 record must be an object"
        )
    except (UnicodeError, json.JSONDecodeError):
        _reject(LABEL_CLOSURE, "g7 record is not JSON")
    if set(document) != set(_G7_FIELDS):
        _reject(LABEL_CLOSURE, "g7 record has the wrong fields")
    if document.get("agents") != list(_G7_AGENTS):
        _reject(LABEL_CLOSURE, "g7 record must name A07, A08 and A09")
    g7_state = document.get("state")
    if g7_state not in {"TESTED", "COMMISSIONED"}:
        _reject(LABEL_CLOSURE, "g7 record state must be TESTED or COMMISSIONED")
    if (
        not isinstance(document.get("g7_go_record_sha256"), str)
        or _SHA256.fullmatch(cast(str, document["g7_go_record_sha256"])) is None
    ):
        _reject(LABEL_CLOSURE, "g7 record needs a go-record sha256")
    approved_at = document.get("approved_at")
    if not isinstance(approved_at, str) or _RFC3339_Z.fullmatch(approved_at) is None:
        _reject(LABEL_CLOSURE, "g7 record needs an RFC3339 Z approved_at")
    agents_blob = _blob_bytes(repo_root, commit, _AGENTS_PATH).decode("utf-8")
    loaded: object = cast(object, yaml.safe_load(agents_blob))
    root = _as_object(loaded, LABEL_CLOSURE, "agents.yaml must be an object")
    rows = root.get("agents")
    if not isinstance(rows, list):
        _reject(LABEL_CLOSURE, "agents.yaml has no agent list")
    by_id: dict[str, dict[str, object]] = {}
    for row in rows:
        body = _as_object(row, LABEL_CLOSURE, "agent row must be an object")
        agent_id = body.get("agent_id")
        if isinstance(agent_id, str):
            by_id[agent_id] = body
    for agent_id in _G7_AGENTS:
        row = by_id.get(agent_id)
        if row is None or row.get("commissioning_state") != g7_state:
            _reject(LABEL_CLOSURE, f"{agent_id} is not at the g7 commissioning state")
        locators = row.get("commissioning_evidence")
        if not isinstance(locators, list) or not locators:
            _reject(LABEL_CLOSURE, f"{agent_id} needs commissioning evidence locators")
        for locator in locators:
            if not isinstance(locator, str) or locator == "":
                _reject(LABEL_CLOSURE, f"{agent_id} locator must be a path")
            _blob_bytes(repo_root, commit, locator)


def verify_record_closure_git(
    repo_root: Path,
    previous: ControlState,
    current: ControlState,
    *,
    writing_commit: str,
    runtime: bool,
) -> None:
    """Check closure commit C. ``runtime`` also requires HEAD == C."""
    commit = current["head_sha"]
    if not isinstance(commit, str):
        _reject(LABEL_CLOSURE, "head_sha must be the closure commit")
    _resolve_commit(repo_root, commit, "closure commit")
    document = _state_document_at(repo_root, commit)
    if document.get("head_sha") == commit or document.get("evidence_closure_commit_sha") == commit:
        raise ControlStateError(CLOSURE_NAMES_ITSELF)
    if document != _raw(previous):
        raise ControlStateError(CLOSURE_STATE_MISMATCH)
    if not _is_ancestor(repo_root, S07_CLOSE_TIP, commit):
        _reject(LABEL_CLOSURE, "the session 07 close tip must be an ancestor of the closure commit")
    if runtime:
        _assert_repo_at_closure(repo_root, commit, current["branch"])
    elif not _is_first_parent_ancestor(repo_root, commit, writing_commit):
        _reject(
            LABEL_CLOSURE,
            "closure commit must be a first-parent ancestor of the writing commit",
        )
    block = _citation_block(current, LABEL_CLOSURE, required=True)
    assert block is not None
    current_map = _session_citation_map(block, LABEL_CLOSURE)
    citation = _as_object(
        current_map[CLOSURE_KEY], LABEL_CLOSURE, "closure citation must be an object"
    )
    _check_g7(repo_root, commit, citation)
    verify_record_evidence_git(repo_root, previous, head_commit=writing_commit)


def verify_revoke_evidence_git(repo_root: Path, current: ControlState, *, head_commit: str) -> None:
    """Re-check citations that remain after a revoke."""
    evidence = _require_evidence_shape(current, LABEL_REVOKE)
    if any(evidence[key] is True for key in NON_CLOSURE_KEYS):
        verify_record_evidence_git(repo_root, current, head_commit=head_commit)


def _assert_attached_clean(repo_root: Path, branch: str) -> str:
    head = _git(repo_root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    actual = _git(repo_root, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    if actual != branch:
        raise ControlStateError("repository HEAD must be attached to the recorded branch")
    status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=no").stdout
    if status:
        raise ControlStateError("all tracked repository files must be clean before transition")
    return head


def apply_record_evidence_transition(state_path: Path, candidate_path: Path) -> ControlState:
    """Record one or more Session 07 evidence keys false to true."""

    def verify(path: Path, previous: ControlState, current: ControlState) -> None:
        del previous
        repo_root, _branch = _validate_repo_identity(path, current)
        head = _assert_attached_clean(repo_root, current["branch"])
        verify_record_evidence_git(repo_root, current, head_commit=head)

    return _apply_transition(
        state_path, candidate_path, validate_record_evidence_transition, verify
    )


def apply_record_closure_transition(state_path: Path, candidate_path: Path) -> ControlState:
    """Record the Session 07 closure commit and align both commit fields to it."""

    def verify(path: Path, previous: ControlState, current: ControlState) -> None:
        repo_root, _branch = _validate_repo_identity(path, current)
        head = _git(repo_root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
        verify_record_closure_git(
            repo_root,
            previous,
            current,
            writing_commit=head,
            runtime=True,
        )

    return _apply_transition(state_path, candidate_path, validate_record_closure_transition, verify)


def apply_revoke_evidence_transition(state_path: Path, candidate_path: Path) -> ControlState:
    """Revoke cited Session 07 evidence keys. Refused after closure."""

    def verify(path: Path, previous: ControlState, current: ControlState) -> None:
        del previous
        repo_root, _branch = _validate_repo_identity(path, current)
        head = _assert_attached_clean(repo_root, current["branch"])
        verify_revoke_evidence_git(repo_root, current, head_commit=head)

    return _apply_transition(
        state_path, candidate_path, validate_revoke_evidence_transition, verify
    )


def _refuse_if_shallow(repo_root: Path) -> None:
    probe = _git(repo_root, "rev-parse", "--is-shallow-repository")
    if probe.stdout.strip() == "true":
        raise ControlStateError(SHALLOW_REPLAY)


def _resolve_anchor(repo_root: Path, anchor: str) -> None:
    try:
        _resolve_commit(repo_root, anchor, "replay anchor")
    except ControlStateError as error:
        raise ControlStateError(ANCHOR_UNRESOLVED) from error


def _is_first_parent_ancestor(repo_root: Path, ancestor: str, descendant: str) -> bool:
    listed = _git(repo_root, "rev-list", "--first-parent", descendant).stdout.splitlines()
    return ancestor in listed


def _is_merge_commit(repo_root: Path, commit: str) -> bool:
    line = _git(repo_root, "rev-list", "--parents", "-n", "1", commit).stdout.strip()
    return len(line.split()) > 2


def _parsed_state(blob: bytes) -> ControlState:
    try:
        decoded = cast(object, json.loads(blob.decode("utf-8")))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ControlStateError(INVALID_STEP) from error
    if not isinstance(decoded, dict):
        raise ControlStateError(INVALID_STEP)
    return cast(ControlState, decoded)


def _assert_anchor_fixture(blob: bytes) -> None:
    if not _FIXTURE_PATH.is_file():
        raise ControlStateError(FIXTURE_MISMATCH)
    fixture = _FIXTURE_PATH.read_bytes()
    if blob == fixture:
        return
    try:
        anchor = cast(object, json.loads(blob.decode("utf-8")))
        expected = cast(object, json.loads(fixture.decode("utf-8")))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ControlStateError(FIXTURE_MISMATCH) from error
    if not isinstance(anchor, dict) or not isinstance(expected, dict):
        raise ControlStateError(FIXTURE_MISMATCH)
    anchor_map = cast(dict[str, object], anchor)
    expected_map = cast(dict[str, object], expected)
    if set(anchor_map) != set(expected_map):
        raise ControlStateError(FIXTURE_MISMATCH)
    drifted = {key for key in anchor_map if anchor_map[key] != expected_map[key]}
    if not drifted <= {"repo_root", "branch"}:
        raise ControlStateError(FIXTURE_MISMATCH)


def _record_step(
    repo_root: Path, previous: ControlState, current: ControlState, commit: str
) -> bool:
    try:
        validate_record_evidence_transition(previous, current)
        verify_record_evidence_git(repo_root, current, head_commit=commit)
    except ControlStateError:
        return False
    return True


def _closure_step(
    repo_root: Path, previous: ControlState, current: ControlState, commit: str
) -> bool:
    try:
        validate_record_closure_transition(previous, current)
        verify_record_closure_git(
            repo_root,
            previous,
            current,
            writing_commit=commit,
            runtime=False,
        )
    except ControlStateError:
        return False
    return True


def _revoke_step(
    repo_root: Path, previous: ControlState, current: ControlState, commit: str
) -> bool:
    try:
        validate_revoke_evidence_transition(previous, current)
        verify_revoke_evidence_git(repo_root, current, head_commit=commit)
    except ControlStateError:
        return False
    return True


def _activation_step(previous: ControlState, current: ControlState) -> bool:
    try:
        validate_activation_transition(previous, current)
    except ControlStateError:
        return False
    return current["current_session"] == 8


def replay_state_history(
    repo_root: Path,
    anchor: str,
    *,
    require_closed_window: bool = False,
) -> ControlState:
    """Replay first-parent Session 07 state history from ``anchor``.

    The anchor argument is chosen by the caller. The CLI and public transitions pass
    ``REPLAY_ANCHOR_SHA`` and never consult the environment.
    """
    _refuse_if_shallow(repo_root)
    _resolve_anchor(repo_root, anchor)
    head = _git(repo_root, "rev-parse", "--verify", "HEAD^{commit}").stdout.strip()
    if not _is_first_parent_ancestor(repo_root, anchor, head):
        raise ControlStateError(ANCHOR_NOT_ANCESTOR)
    anchor_blob = _blob_bytes(repo_root, anchor, _STATE_RELATIVE)
    _assert_anchor_fixture(anchor_blob)
    listed = _git(
        repo_root,
        "log",
        "--first-parent",
        "--reverse",
        "--format=%H",
        f"{anchor}..HEAD",
        "--",
        _STATE_RELATIVE,
    ).stdout.splitlines()
    commits = [anchor, *[line for line in listed if line]]
    states = [_parsed_state(_blob_bytes(repo_root, commit, _STATE_RELATIVE)) for commit in commits]
    end_index: int | None = None
    for index, state in enumerate(states):
        if index == 0:
            continue
        if state["current_session"] != 7:
            end_index = index
            break
    if end_index is None and require_closed_window:
        raise ControlStateError(NO_WINDOW)
    last_index = end_index if end_index is not None else len(commits) - 1
    for index in range(1, last_index + 1):
        commit = commits[index]
        previous = states[index - 1]
        current = states[index]
        if _is_merge_commit(repo_root, commit):
            raise ControlStateError(SQUASH_REQUIRED)
        is_end = end_index is not None and index == end_index
        if is_end:
            try:
                validate_activation_transition(previous, current)
            except ControlStateError as error:
                raise ControlStateError(f"{BAD_WINDOW}: {error}") from error
        matches: list[str] = []
        if _record_step(repo_root, previous, current, commit):
            matches.append("record")
        if _closure_step(repo_root, previous, current, commit):
            matches.append("closure")
        if _revoke_step(repo_root, previous, current, commit):
            matches.append("revoke")
        if _activation_step(previous, current):
            matches.append("activation")
        if is_end and "activation" not in matches:
            raise ControlStateError(BAD_WINDOW)
        if not is_end and "activation" in matches:
            raise ControlStateError(INVALID_STEP)
        if len(matches) != 1:
            raise ControlStateError(INVALID_STEP)
    tip = states[end_index - 1] if end_index is not None else states[-1]
    if end_index is None:
        worktree = (repo_root / CANONICAL_STATE_RELATIVE_PATH).read_bytes()
        if worktree != _blob_bytes(repo_root, head, _STATE_RELATIVE):
            raise ControlStateError(WORKTREE_MISMATCH)
    return tip


def replay_for_activation(
    current: ControlState,
    replay_anchor: str | None,
    *,
    require_closed_window: bool,
) -> None:
    """Replay before an activation into session 8 or 9. ``None`` selects the hardcoded anchor."""
    anchor = REPLAY_ANCHOR_SHA if replay_anchor is None else replay_anchor
    replay_state_history(
        Path(current["repo_root"]),
        anchor,
        require_closed_window=require_closed_window,
    )


def assert_session_seven_tip(state: Mapping[str, object]) -> None:
    """Pin the Session 07 tip's citations and commit fields. No git access."""
    evidence = state.get("required_completion_evidence")
    if not isinstance(evidence, dict):
        raise ControlStateError(CITATION_REQUIRED)
    evidence_map = cast(dict[object, object], evidence)
    citations = state.get("evidence_citations")
    cited: dict[object, object] = {}
    if isinstance(citations, dict):
        session_citations = cast(dict[object, object], citations).get("7")
        if isinstance(session_citations, dict):
            cited = cast(dict[object, object], session_citations)
    true_keys = [key for key, value in evidence_map.items() if value is True]
    if not all(key in cited for key in true_keys):
        raise ControlStateError(CITATION_REQUIRED)
    head = state.get("head_sha")
    closure = state.get("evidence_closure_commit_sha")
    if evidence_map.get(CLOSURE_KEY) is True:
        citation = cited.get(CLOSURE_KEY)
        if not isinstance(citation, dict):
            raise ControlStateError(CLOSURE_CITATION_PINS)
        expected = cast(dict[object, object], citation).get("closure_commit")
        if head != expected or closure != expected:
            raise ControlStateError(CLOSURE_CITATION_PINS)
        return
    if head != S07_CLOSE_TIP or closure != S06_PRIOR_WAVE_TIP or head == closure:
        raise ControlStateError(PRE_CLOSURE_PINS)


def assert_session_seven_continuity(repo_root: Path) -> None:
    """Replay the real history from the hardcoded anchor and pin that tip."""
    tip = replay_state_history(repo_root, REPLAY_ANCHOR_SHA, require_closed_window=False)
    assert_session_seven_tip(_raw(tip))
