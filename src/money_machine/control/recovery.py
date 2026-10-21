"""D-0039's single audited recovery; ordinary session guards remain unchanged."""

from __future__ import annotations

# Package-internal reuse preserves the existing transition lock and atomic writer.
# pyright: reportPrivateUsage=false
import base64
import copy
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from money_machine.control.state import (
    CANONICAL_STATE_RELATIVE_PATH,
    SESSION_EVIDENCE_KEYS,
    SESSION_PROMPTS,
    ControlStateError,
    _atomic_write_json,
    _git,
    _parse_state,
    _resolve_commit,
    _state_transition_lock,
)

LEGACY_STATE_SHA256 = "fc0fb4143c8fdfaaa81abfb9cca32687d42eb92e8979cfa0c9a911460886a624"
_OPERATOR_CLOSE = "b782751fdb1b255c436ff7f6fa655e6d783b1e8c"
_DECISION = Path("docs/control/DECISIONS.md")
_ADDENDUM = Path("docs/control/reviews/2026-10-22-one-real-draft-prompt-integrity.md")
_DECISION_SHA256 = "f712f638eff6773823ff5a4019ce8ba5cae178828c99e07efd6441d2eafd6671"
_ADDENDUM_SHA256 = "cbac987af7ad93a2c0c4f768fa3d75f50b97f88ececd594036aaa1465c73cec7"


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _payload(document: dict[str, object]) -> bytes:
    return (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode()


def _no_symlinks(path: Path) -> Path:
    absolute = path.absolute()
    if any(part.is_symlink() for part in (absolute, *absolute.parents)):
        raise ControlStateError("recovery paths must not contain a symlink")
    return absolute.resolve()


def _candidate(previous: dict[str, object], root: Path, timestamp: str) -> dict[str, object]:
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        previous_time = datetime.fromisoformat(str(previous["updated_at"]).replace("Z", "+00:00"))
        if parsed.utcoffset() is None or parsed <= previous_time or parsed > datetime.now(UTC):
            raise ValueError("invalid recovery timestamp")
    except (ValueError, TypeError) as error:
        raise ControlStateError("invalid recovery timestamp") from error
    if (
        previous["repo_root"] != "/mnt/d/Money Machine"
        or previous["branch"] != "build/full-automation"
        or previous["current_session"] != 7
        or previous["state_revision"] != 64
        or previous["session_status"] != "complete"
        or previous["completed_sessions"] != list(range(8))
        or previous["head_sha"] != _OPERATOR_CLOSE
        or previous["commissioned_agents"] != []
        or previous["required_completion_evidence"]
        != dict.fromkeys(SESSION_EVIDENCE_KEYS[7], False)
    ):
        raise ControlStateError("only the exact unproved Session 07 legacy state is recoverable")
    candidate = copy.deepcopy(previous)
    contract = cast(dict[str, object], candidate["transition_contract"])
    contract["completion_requires_next_session"] = 8
    candidate.update(
        repo_root=str(root),
        state_revision=65,
        session_status="incomplete",
        completed_sessions=list(range(7)),
        next_session=7,
        next_prompt=SESSION_PROMPTS[7],
        head_sha=previous["evidence_closure_commit_sha"],
        updated_at=timestamp,
    )
    return candidate


def _authority(root: Path) -> None:
    for path in (_DECISION, _ADDENDUM):
        current = _no_symlinks(root / path).read_text(encoding="utf-8")
        committed = _git(root, "show", f"HEAD:{path.as_posix()}").stdout
        if current != committed:
            raise ControlStateError("recovery authority must be committed and unchanged")
        if path == _DECISION:
            marker = "## D-0039"
            if current.count(marker) != 1:
                raise ControlStateError("committed D-0039 recovery authority is missing")
            section = marker + current.split(marker, 1)[1].split("\n## ", 1)[0]
            valid = _sha(section.strip().encode()) == _DECISION_SHA256
        else:
            valid = _sha(current.encode()) == _ADDENDUM_SHA256
        if not valid:
            raise ControlStateError("recovery authority differs from reviewed D-0039/addendum")


def _repository(root: Path, head: str, previous: dict[str, object], *, replay: bool) -> Path:
    actual = Path(_git(root, "rev-parse", "--show-toplevel").stdout.strip()).resolve()
    if actual != root:
        raise ControlStateError("recovery root must be the canonical Git worktree root")
    if _git(root, "rev-parse", "HEAD").stdout.strip() != head:
        raise ControlStateError("repository HEAD differs from expected HEAD")
    branch = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip()
    if branch != previous["branch"]:
        raise ControlStateError("recovery requires the clean recorded trunk branch")
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all").stdout
    # The lock is transient; the only replay difference allowed is our exact candidate state.
    lock = f"?? docs/control/.{CANONICAL_STATE_RELATIVE_PATH.name}.lock"
    lines = [line for line in status.splitlines() if line != lock]
    allowed = [f" M {CANONICAL_STATE_RELATIVE_PATH.as_posix()}"]
    if lines and not (replay and lines == allowed):
        raise ControlStateError("recovery requires a clean repository (including untracked files)")
    committed = _git(root, "show", f"HEAD:{CANONICAL_STATE_RELATIVE_PATH.as_posix()}").stdout
    if _sha(committed.encode()) != LEGACY_STATE_SHA256:
        raise ControlStateError("HEAD must contain the exact legacy state")
    _authority(root)
    for field in ("bootstrap_commit_sha", "evidence_closure_commit_sha", "head_sha"):
        commit = str(previous[field])
        _resolve_commit(root, commit, field)
        _git(root, "merge-base", "--is-ancestor", commit, head)
    _git(
        root,
        "merge-base",
        "--is-ancestor",
        str(previous["bootstrap_commit_sha"]),
        str(previous["evidence_closure_commit_sha"]),
    )
    git_directory = _no_symlinks(Path(_git(root, "rev-parse", "--absolute-git-dir").stdout.strip()))
    return git_directory / "control-recovery"


def _read_intent(path: Path, root: Path, head: str) -> dict[str, object]:
    try:
        document = cast(dict[str, object], json.loads(_no_symlinks(path).read_text()))
        raw = base64.b64decode(str(document["before_base64"]), validate=True)
        previous = cast(dict[str, object], json.loads(raw))
        expected = _candidate(previous, root, str(document["timestamp"]))
        if (
            _sha(raw) != LEGACY_STATE_SHA256
            or document["before_sha256"] != LEGACY_STATE_SHA256
            or document["expected_head"] != head
            or document["repo_root"] != str(root)
            or document["candidate"] != expected
            or document["after_sha256"] != _sha(_payload(expected))
            or document["operator_close"]
            != {
                "head_sha": previous["head_sha"],
                "notes": previous.get("notes"),
                "session_status": previous["session_status"],
                "state_revision": 64,
            }
        ):
            raise ValueError("intent does not match the authorized recovery")
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise ControlStateError("recovery intent receipt is invalid") from error
    return document


def recover_session_seven(
    state_path: Path,
    *,
    repo_root: Path,
    expected_before_sha: str | None = None,
    expected_head: str | None = None,
    apply: bool = False,
) -> dict[str, object]:
    """Preview by default; apply only the exact D-0039 recovery with durable provenance."""
    if apply and (expected_before_sha is None or expected_head is None):
        raise ControlStateError("apply requires explicit expected before SHA-256 and expected HEAD")
    if expected_before_sha is not None and expected_before_sha != LEGACY_STATE_SHA256:
        raise ControlStateError("expected before SHA-256 is not the authorized legacy state")
    root = _no_symlinks(repo_root)
    state_path = _no_symlinks(state_path)
    if state_path != root / CANONICAL_STATE_RELATIVE_PATH or not state_path.is_file():
        raise ControlStateError("state must be the canonical file within the recovery root")
    head = expected_head or _git(root, "rev-parse", "HEAD").stdout.strip()
    with _state_transition_lock(state_path):
        try:
            _, current = _parse_state(state_path, "recovery state")
            raw = state_path.read_bytes()
            git_directory = Path(_git(root, "rev-parse", "--absolute-git-dir").stdout.strip())
            receipt_directory = _no_symlinks(git_directory / "control-recovery")
            intent_path = _no_symlinks(receipt_directory / f"{LEGACY_STATE_SHA256}.intent.json")
            final_path = _no_symlinks(receipt_directory / f"{LEGACY_STATE_SHA256}.applied.json")
            intent: dict[str, object]
            reconciled = intent_path.exists()
            if reconciled:
                intent = _read_intent(intent_path, root, head)
                previous = cast(
                    dict[str, object], json.loads(base64.b64decode(str(intent["before_base64"])))
                )
                candidate = cast(dict[str, object], intent["candidate"])
                if raw not in (base64.b64decode(str(intent["before_base64"])), _payload(candidate)):
                    raise ControlStateError("state differs from both recovery intent and candidate")
            else:
                if _sha(raw) != LEGACY_STATE_SHA256:
                    raise ControlStateError(
                        "current state SHA-256 differs from authorized legacy state"
                    )
                previous = current
                timestamp = datetime.now(UTC).isoformat().replace("+00:00", "Z")
                candidate = _candidate(previous, root, timestamp)
                intent = {
                    "before_sha256": LEGACY_STATE_SHA256,
                    "before_base64": base64.b64encode(raw).decode(),
                    "after_sha256": _sha(_payload(candidate)),
                    "candidate": candidate,
                    "timestamp": timestamp,
                    "repo_root": str(root),
                    "expected_head": head,
                    "authority": "D-0039",
                    "operator_close": {
                        "head_sha": previous["head_sha"],
                        "notes": previous.get("notes"),
                        "session_status": previous["session_status"],
                        "state_revision": 64,
                    },
                }
            _repository(root, head, previous, replay=reconciled)
            if final_path.exists():
                final = json.loads(final_path.read_text())
                if final != {
                    "before_sha256": LEGACY_STATE_SHA256,
                    "after_sha256": intent["after_sha256"],
                    "expected_head": head,
                }:
                    raise ControlStateError("final recovery receipt differs from the intent")
                if raw != _payload(candidate):
                    raise ControlStateError("final recovery receipt exists without recovered state")
            if apply:
                if not reconciled:
                    receipt_directory.mkdir(mode=0o700, exist_ok=True)
                    if hasattr(os, "O_DIRECTORY"):
                        descriptor = os.open(receipt_directory.parent, os.O_RDONLY | os.O_DIRECTORY)
                        try:
                            os.fsync(descriptor)
                        finally:
                            os.close(descriptor)
                    # _atomic_write_json fsyncs the payload and parent before state replacement.
                    _atomic_write_json(intent_path, intent)
                if raw != _payload(candidate):
                    _atomic_write_json(state_path, candidate)
                _atomic_write_json(
                    final_path,
                    {
                        "before_sha256": LEGACY_STATE_SHA256,
                        "after_sha256": intent["after_sha256"],
                        "expected_head": head,
                    },
                )
            return {
                "applied": apply,
                "reconciled": reconciled,
                "candidate": candidate,
                "before_sha256": LEGACY_STATE_SHA256,
                "after_sha256": intent["after_sha256"],
                "expected_head": head,
                "receipt_path": str(intent_path),
            }
        except (OSError, json.JSONDecodeError) as error:
            raise ControlStateError(f"recovery write/read failed: {error}") from error
