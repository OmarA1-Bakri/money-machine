# The frozen ControlState TypedDict cannot name evidence_citations. These tests
# mutate that JSON object anyway, and they pass it to the test helper's writer.
# pyright: reportArgumentType=false, reportGeneralTypeIssues=false, reportUnnecessaryCast=false
"""Killing tests for Session 07 record-evidence, record-closure, revoke-evidence, and replay.

Tests 1-36, 38-44, 48, and 49 live here. Test 37 is the frozen #66 re-proof in
``test_control_state.py``. Tests 45-47 live beside this module. Nothing here
writes ``docs/control/IMPLEMENTATION_STATE.json`` in the real worktree.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

import pytest
import yaml

from money_machine.cli.notion_sandbox_guard import SANDBOX_PARENT_PAGE_ID, SANDBOX_SPACE_ID
from money_machine.control import state as control_state
from money_machine.control.s07_evidence import (
    CLOSURE_CITATION_PINS,
    CLOSURE_KEY,
    CLOSURE_NAMES_ITSELF,
    CLOSURE_STATE_MISMATCH,
    NON_CLOSURE_KEYS,
    ONE_STATE_TRANSITION,
    PRE_CLOSURE_PINS,
    REBASE_NOT_MERGE,
    S06_PRIOR_WAVE_TIP,
    S07_CLOSE_TIP,
    S07_EVIDENCE_KINDS,
    WORKTREE_MISMATCH,
    ControlStateError,
    assert_pull_request_state_transitions,
    assert_session_seven_continuity,
    assert_session_seven_tip,
    replay_state_history,
    validate_record_closure_transition,
    validate_record_evidence_transition,
    validate_revoke_evidence_transition,
    verify_record_closure_git,
    verify_record_evidence_git,
    verify_revoke_evidence_git,
)
from money_machine.control.state import (
    SESSION_EVIDENCE_KEYS,
    SESSION_PROMPTS,
    ControlState,
    _apply_activation_transition,  # pyright: ignore[reportPrivateUsage]
    _apply_completion_transition,  # pyright: ignore[reportPrivateUsage]
    apply_activation_transition,
    apply_record_closure_transition,
    apply_record_evidence_transition,
    apply_revoke_evidence_transition,
    validate_activation_transition,
    validate_completion_transition,
)
from tests.bootstrap.test_control_state import (
    SESSION_08_EVIDENCE_KEYS,
    load_rev64_fixture,
    prepare_completed_session_zero,
    write_state,
)

ROOT = Path(__file__).resolve().parents[2]
STATE_FILE = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
REAL_STATE_BYTES = STATE_FILE.read_bytes()
BRANCH = "build/full-automation"
BOOTSTRAP = "1abf0d7cca3a6b8cd7efcd0a45523538fd5bfd9d"
KEY_ONE = "notion_product_builder_implemented"
KEY_TWO = "shared_databases_built"
KEY_THREE = "home_dashboard_built"
KEY_ELEVEN = "control_files_and_checkpoint_current"
DIGEST = "b" * 64
NEW_COMMIT = "c" * 40
OTHER_COMMIT = "d" * 40
NARRATIVE = (
    "docs/control/IMPLEMENTATION_LOG.md",
    "docs/control/NEXT_SESSION.md",
    "docs/control/TEST_EVIDENCE.md",
    "docs/control/DECISIONS.md",
)
RECORD_MUTABLE = frozenset({"state_revision", "updated_at", "required_completion_evidence"})
CLOSURE_MUTABLE = RECORD_MUTABLE | {"head_sha", "evidence_closure_commit_sha"}
Validator = Callable[[ControlState, ControlState], None]
VALIDATORS: dict[str, Validator] = {
    "record": validate_record_evidence_transition,
    "closure": validate_record_closure_transition,
    "revoke": validate_revoke_evidence_transition,
}


@dataclass
class Anchor:
    repo: Path
    sha: str
    state: ControlState
    tmp_path: Path


@pytest.fixture(autouse=True)
def _real_state_stays_byte_identical() -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    yield
    assert STATE_FILE.read_bytes() == REAL_STATE_BYTES


def _fresh() -> ControlState:
    return cast(ControlState, copy.deepcopy(load_rev64_fixture()))


def _advance(state: ControlState, stamp: str = "2026-10-10T12:30:00Z") -> ControlState:
    current = copy.deepcopy(state)
    current["state_revision"] = state["state_revision"] + 1
    current["updated_at"] = stamp
    return current


def _citation(key: str, merge: str = "a" * 40, digest: str = DIGEST) -> dict[str, object]:
    return {
        "pr": 70,
        "merge_commit": merge,
        "manifest": f"docs/evidence/s07/{key}/manifest.json",
        "manifest_blob_sha256": digest,
        "ci_run": "ci-test",
        "recorded_at": "2026-10-10T12:00:00Z",
    }


def _closure_citation(commit: str) -> dict[str, object]:
    return {
        "closure_commit": commit,
        "recorded_at": "2026-10-10T12:40:00Z",
        "g7_record_blob_sha256": DIGEST,
    }


def _evidence(state: ControlState) -> dict[str, bool]:
    return cast(dict[str, bool], state["required_completion_evidence"])


def _citations(state: ControlState) -> dict[str, object]:
    return cast(dict[str, object], state["evidence_citations"])


def _valid_record() -> tuple[ControlState, ControlState]:
    previous = _fresh()
    current = _advance(previous)
    _evidence(current)[KEY_ONE] = True
    current["evidence_citations"] = {"7": {KEY_ONE: _citation(KEY_ONE)}}
    return previous, current


def _eleven(previous: ControlState | None = None) -> ControlState:
    state = _fresh() if previous is None else copy.deepcopy(previous)
    evidence = _evidence(state)
    cited: dict[str, object] = {}
    for key in NON_CLOSURE_KEYS:
        evidence[key] = True
        cited[key] = _citation(key)
    evidence[CLOSURE_KEY] = False
    state["evidence_citations"] = {"7": cited}
    state["head_sha"] = S07_CLOSE_TIP
    state["evidence_closure_commit_sha"] = S06_PRIOR_WAVE_TIP
    return state


def _valid_closure() -> tuple[ControlState, ControlState]:
    previous = _eleven()
    current = _advance(previous, "2026-10-10T12:40:00Z")
    _evidence(current)[CLOSURE_KEY] = True
    current["head_sha"] = NEW_COMMIT
    current["evidence_closure_commit_sha"] = NEW_COMMIT
    cited = cast(dict[str, object], _citations(current)["7"])
    cited[CLOSURE_KEY] = _closure_citation(NEW_COMMIT)
    return previous, current


def _valid_revoke() -> tuple[ControlState, ControlState]:
    previous = _fresh()
    _evidence(previous)[KEY_THREE] = True
    previous["evidence_citations"] = {"7": {KEY_THREE: _citation(KEY_THREE)}}
    current = _advance(previous, "2026-10-10T12:50:00Z")
    _evidence(current)[KEY_THREE] = False
    current["evidence_citations"] = {
        "7": {},
        "7_revoked": [
            {
                "key": KEY_THREE,
                "reason": "recorded against the wrong manifest",
                "revoked_at": "2026-10-10T12:50:00Z",
                "revoked_in_rev": current["state_revision"],
            }
        ],
    }
    return previous, current


def _expect(command: str, previous: ControlState, current: ControlState, fragment: str) -> None:
    with pytest.raises(ControlStateError, match=re.escape(fragment)):
        VALIDATORS[command](previous, current)


def _perturb(value: object) -> object:
    if isinstance(value, str):
        if re.fullmatch(r"[0-9a-f]{40}", value):
            return OTHER_COMMIT if value == NEW_COMMIT else NEW_COMMIT
        return value + "-changed"
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, list):
        return [*value, "changed"]
    if isinstance(value, dict):
        changed = dict(value)
        changed["changed"] = True
        return changed
    if value is None:
        return NEW_COMMIT
    raise AssertionError(type(value))


def test_01_incomplete_session_is_refused() -> None:
    previous, current = _valid_record()
    previous["session_status"] = "incomplete"
    current["session_status"] = "incomplete"
    _expect("record", previous, current, "the session must be complete")


def test_valid_structural_steps_are_accepted() -> None:
    """A refuse-everything mutant dies because each command accepts one valid step."""
    record_previous, record_current = _valid_record()
    validate_record_evidence_transition(record_previous, record_current)
    closure_previous, closure_current = _valid_closure()
    validate_record_closure_transition(closure_previous, closure_current)
    revoke_previous, revoke_current = _valid_revoke()
    validate_revoke_evidence_transition(revoke_previous, revoke_current)


def test_02_every_non_mutable_field_is_refused() -> None:
    """Immutable fields are fixture keys minus that command's mutable set."""
    fixture_keys = set(_fresh())
    commands = {
        "record": (_valid_record, RECORD_MUTABLE),
        "closure": (_valid_closure, CLOSURE_MUTABLE),
        "revoke": (_valid_revoke, RECORD_MUTABLE),
    }
    for command, (builder, mutable) in commands.items():
        fields = fixture_keys - mutable
        if command == "closure":
            assert "head_sha" not in fields
            assert "evidence_closure_commit_sha" not in fields
        assert fields
        for field in sorted(fields):
            previous, current = builder()
            current[field] = cast(object, _perturb(current[field]))
            _expect(command, previous, current, f"{field} cannot change")


def test_03_record_evidence_cannot_flip_true_to_false() -> None:
    previous, _current = _valid_record()
    validate_record_evidence_transition(previous, _current)
    later = _advance(_current, "2026-10-10T12:31:00Z")
    _evidence(later)[KEY_ONE] = False
    _expect("record", _current, later, "evidence cannot change from true to false")


def test_04_an_uncited_flip_is_refused() -> None:
    previous, current = _valid_record()
    current["evidence_citations"] = {"7": {}}
    _expect("record", previous, current, f"{KEY_ONE} is true without a citation")


def test_05_a_citation_for_a_false_key_is_refused() -> None:
    previous, current = _valid_record()
    cast(dict[str, object], _citations(current)["7"])[KEY_TWO] = _citation(KEY_TWO)
    _expect("record", previous, current, f"{KEY_TWO} is false but cited")


def test_06_citations_outside_session_07_are_refused() -> None:
    previous, current = _valid_record()
    current["evidence_citations"] = {"8": {KEY_ONE: _citation(KEY_ONE)}}
    _expect("record", previous, current, "evidence_citations keys must be 7 or 7 and 7_revoked")
    _previous, other = _valid_record()
    other["evidence_citations"] = {"6": {KEY_ONE: _citation(KEY_ONE)}}
    _expect("record", previous, other, "evidence_citations keys must be 7 or 7 and 7_revoked")
    _previous, outside = _valid_record()
    cast(dict[str, object], _citations(outside)["7"])["not_a_session_07_key"] = _citation(
        "not_a_session_07_key"
    )
    _expect("record", previous, outside, "citation names a key outside session 07")


def test_07_citations_cannot_be_removed_or_created_again() -> None:
    _previous, current = _valid_record()
    removed = _advance(current, "2026-10-10T12:32:00Z")
    del removed["evidence_citations"]
    _evidence(removed)[KEY_TWO] = True
    _expect("record", current, removed, "evidence_citations cannot be removed")
    first = _fresh()
    created = _advance(first)
    _evidence(created)[KEY_ONE] = True
    created["evidence_citations"] = {
        "7": {KEY_ONE: _citation(KEY_ONE)},
        "7_revoked": [],
    }
    _expect(
        "record", first, created, "the first record may create only the session 07 citation map"
    )
    again = _advance(current, "2026-10-10T12:33:00Z")
    _evidence(again)[KEY_TWO] = True
    block = cast(dict[str, object], copy.deepcopy(again["evidence_citations"]))
    block["7_revoked"] = []
    again["evidence_citations"] = block
    _expect("record", current, again, "evidence_citations keys cannot be added or removed")


def test_08_revision_and_timestamp_are_refused_by_every_command() -> None:
    builders = {"record": _valid_record, "closure": _valid_closure, "revoke": _valid_revoke}
    for command, builder in builders.items():
        previous, plus_zero = builder()
        plus_zero["state_revision"] = previous["state_revision"]
        _expect(command, previous, plus_zero, "state revision must advance exactly once")
        _previous, plus_two = builder()
        plus_two["state_revision"] = previous["state_revision"] + 2
        _expect(command, previous, plus_two, "state revision must advance exactly once")
        _previous, same_time = builder()
        same_time["updated_at"] = previous["updated_at"]
        _expect(command, previous, same_time, "updated_at must change")


def test_09_evidence_values_and_key_set_are_strict() -> None:
    for bad in ("true", 1, None):
        previous, current = _valid_record()
        cast(dict[str, object], current["required_completion_evidence"])[KEY_TWO] = bad
        _expect("record", previous, current, "evidence values must be booleans")
    previous, unchanged = _valid_record()
    cast(dict[str, object], previous["required_completion_evidence"])[KEY_TWO] = "true"
    cast(dict[str, object], unchanged["required_completion_evidence"])[KEY_TWO] = "true"
    _expect("record", previous, unchanged, "evidence values must be booleans")
    previous, extra = _valid_record()
    _evidence(extra)["extra_evidence_key"] = False
    _expect("record", previous, extra, "evidence keys must equal the session 07 contract")
    _previous, missing = _valid_record()
    del _evidence(missing)[KEY_TWO]
    _expect("record", previous, missing, "evidence keys must equal the session 07 contract")


def test_10_session_nine_has_no_evidence_contract() -> None:
    previous, current = _valid_record()
    previous["current_session"] = 9
    current["current_session"] = 9
    with pytest.raises(ControlStateError, match="no completion evidence contract for session 9"):
        validate_record_evidence_transition(previous, current)


def test_19_key_11_requires_keys_1_through_10() -> None:
    previous, current = _valid_record()
    _evidence(current)[KEY_ONE] = False
    _evidence(current)[KEY_ELEVEN] = True
    current["evidence_citations"] = {"7": {KEY_ELEVEN: _citation(KEY_ELEVEN)}}
    _expect(
        "record",
        previous,
        current,
        "keys 1-10 must already be true before the control-file key",
    )


def test_20_closure_requires_every_non_closure_key_true_and_cited() -> None:
    previous, current = _valid_closure()
    _evidence(previous)[KEY_THREE] = False
    _evidence(current)[KEY_THREE] = False
    _expect("closure", previous, current, "all eleven non-closure keys must be true")
    cited_previous, cited_current = _valid_closure()
    del cast(dict[str, object], _citations(cited_previous)["7"])[KEY_THREE]
    del cast(dict[str, object], _citations(cited_current)["7"])[KEY_THREE]
    _expect("closure", cited_previous, cited_current, f"{KEY_THREE} must stay cited and unchanged")


def test_23_and_24_closure_commit_cannot_be_the_old_pins() -> None:
    previous, as_prior = _valid_closure()
    as_prior["head_sha"] = S06_PRIOR_WAVE_TIP
    as_prior["evidence_closure_commit_sha"] = S06_PRIOR_WAVE_TIP
    cited = cast(dict[str, object], _citations(as_prior)["7"])
    cited[CLOSURE_KEY] = _closure_citation(S06_PRIOR_WAVE_TIP)
    _expect("closure", previous, as_prior, "head_sha cannot be the prior-wave closure")
    _previous, as_tip = _valid_closure()
    as_tip["head_sha"] = S07_CLOSE_TIP
    as_tip["evidence_closure_commit_sha"] = S07_CLOSE_TIP
    tip_cited = cast(dict[str, object], _citations(as_tip)["7"])
    tip_cited[CLOSURE_KEY] = _closure_citation(S07_CLOSE_TIP)
    _expect(
        "closure",
        previous,
        as_tip,
        "evidence_closure_commit_sha cannot be the session 07 close tip",
    )


def test_27_both_commit_fields_must_equal_the_new_closure_commit() -> None:
    previous, current = _valid_closure()
    current["evidence_closure_commit_sha"] = OTHER_COMMIT
    _expect(
        "closure",
        previous,
        current,
        "head_sha and evidence_closure_commit_sha must both equal the closure commit",
    )


def test_28_head_sha_cannot_move_to_the_prior_wave_closure() -> None:
    previous, current = _valid_closure()
    current["head_sha"] = S06_PRIOR_WAVE_TIP
    _expect("closure", previous, current, "head_sha cannot be the prior-wave closure")


def test_29_closure_sha_cannot_move_to_the_session_07_tip() -> None:
    previous, current = _valid_closure()
    current["evidence_closure_commit_sha"] = S07_CLOSE_TIP
    _expect(
        "closure",
        previous,
        current,
        "evidence_closure_commit_sha cannot be the session 07 close tip",
    )


def test_31_record_evidence_cannot_flip_the_closure_key() -> None:
    previous, current = _valid_record()
    _evidence(current)[KEY_ONE] = False
    _evidence(current)[CLOSURE_KEY] = True
    current["evidence_citations"] = {"7": {CLOSURE_KEY: _closure_citation(NEW_COMMIT)}}
    _expect("record", previous, current, "the closure key cannot be recorded by record-evidence")


def test_32_revoke_and_repeat_closure_are_refused() -> None:
    previous, current = _valid_revoke()
    _evidence(previous)[KEY_THREE] = True
    del cast(dict[str, object], _citations(previous)["7"])[KEY_THREE]
    _expect("revoke", previous, current, f"{KEY_THREE} is not cited")

    already = _eleven()
    _evidence(already)[CLOSURE_KEY] = True
    repeat = _advance(already, "2026-10-10T12:41:00Z")
    _expect("closure", already, repeat, "closure is already recorded")

    after = _eleven()
    _evidence(after)[CLOSURE_KEY] = True
    cast(dict[str, object], _citations(after)["7"])[CLOSURE_KEY] = _closure_citation(NEW_COMMIT)
    after["head_sha"] = NEW_COMMIT
    after["evidence_closure_commit_sha"] = NEW_COMMIT
    revoked = _advance(after, "2026-10-10T12:51:00Z")
    _evidence(revoked)[KEY_THREE] = False
    block = cast(dict[str, object], copy.deepcopy(revoked["evidence_citations"]))
    session = cast(dict[str, object], block["7"])
    del session[KEY_THREE]
    block["7_revoked"] = [
        {
            "key": KEY_THREE,
            "reason": "closed session",
            "revoked_at": "2026-10-10T12:51:00Z",
            "revoked_in_rev": revoked["state_revision"],
        }
    ]
    revoked["evidence_citations"] = block
    _expect("revoke", after, revoked, "revoke is refused once the closure key is true")

    open_previous, open_current = _valid_revoke()
    open_current["evidence_citations"] = {
        "7": {},
        "7_revoked": [
            {
                "key": KEY_THREE,
                "reason": "",
                "revoked_at": "2026-10-10T12:50:00Z",
                "revoked_in_rev": open_current["state_revision"],
            }
        ],
    }
    _expect("revoke", open_previous, open_current, "reason must be non-empty")

    _previous, moved = _valid_revoke()
    moved["head_sha"] = NEW_COMMIT
    _expect("revoke", open_previous, moved, "head_sha cannot change")


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
    )
    return completed.stdout.decode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _write_json(path: Path, document: Mapping[str, object]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(document, indent=2) + "\n").encode()
    path.write_bytes(payload)
    return _sha256(payload)


def _clone(tmp_path: Path) -> Path:
    dest = tmp_path / "repo"
    subprocess.run(
        ["git", "clone", "--local", str(ROOT), str(dest)],
        check=True,
        capture_output=True,
    )
    _git(dest, "checkout", "-B", BRANCH)
    _git(dest, "config", "user.name", "S07 Test")
    _git(dest, "config", "user.email", "s07-test@example.invalid")
    _git(dest, "config", "commit.gpgsign", "false")
    _git(dest, "config", "core.hooksPath", "/dev/null")
    return Path(_git(dest, "rev-parse", "--show-toplevel").strip())


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD").strip()


def _anchor(tmp_path: Path) -> Anchor:
    repo = _clone(tmp_path)
    tracked = subprocess.run(
        ["git", "-C", str(repo), "ls-files", "docs/evidence/s07"],
        check=True,
        capture_output=True,
    )
    if tracked.stdout.strip():
        _git(repo, "rm", "-r", "docs/evidence/s07")
    state = _fresh()
    state["repo_root"] = str(repo)
    state["branch"] = BRANCH
    write_state(repo / "docs/control/IMPLEMENTATION_STATE.json", state)
    return Anchor(repo, _commit(repo, "test: rewrite repo identity"), state, tmp_path)


def _run_document(kind: str) -> dict[str, object]:
    document: dict[str, object] = {
        "mode": "execute",
        "redaction_self_check": "PASS",
        "space_id": SANDBOX_SPACE_ID,
        "parent_page_id": SANDBOX_PARENT_PAGE_ID,
    }
    if kind == "p4_qa":
        document["qa_verdict"] = "PASS"
    if kind == "p6_test_record":
        document["test_node_ids"] = ["tests/bootstrap/test_s07_evidence_record.py"]
        document["ci_run"] = "ci-test"
    if kind == "p8a_ci_record":
        document["ci_run"] = "ci-test"
    return document


def _plant(
    repo: Path,
    keys: tuple[str, ...],
    *,
    qa_sha: str | None = None,
    mutate: Callable[[str, dict[str, object]], None] | None = None,
) -> dict[str, dict[str, object]]:
    citations: dict[str, dict[str, object]] = {}
    for key in keys:
        artifacts: list[dict[str, object]] = []
        for kind in sorted(S07_EVIDENCE_KINDS[key]):
            if kind == "p5_ledger":
                document: dict[str, object] = {"qa_record_sha256": qa_sha}
            elif kind == "p8b_control_record":
                document = {
                    "control_file_sha256": {
                        path: _sha256((repo / path).read_bytes()) for path in NARRATIVE
                    }
                }
            else:
                document = _run_document(kind)
            if mutate is not None:
                mutate(kind, document)
            relative = f"docs/evidence/s07/{key}/{kind}.json"
            digest = _write_json(repo / relative, document)
            artifacts.append({"kind": kind, "path": relative, "sha256": digest})
        manifest = {
            "session": 7,
            "key": key,
            "phase": "p0",
            "artifacts": artifacts,
            "reviewer_pass": "pass",
            "verifier_pass": "pass",
            "go_record_sha256": None,
        }
        manifest_path = f"docs/evidence/s07/{key}/manifest.json"
        citations[key] = _citation(key, digest=_write_json(repo / manifest_path, manifest))
    return citations


def _apply_record(
    anchor: Anchor,
    state: ControlState,
    keys: tuple[str, ...],
    citations: Mapping[str, Mapping[str, object]],
    merge: str,
    stamp: str,
) -> ControlState:
    current = _advance(state, stamp)
    evidence = _evidence(current)
    block = cast(dict[str, object], copy.deepcopy(current.get("evidence_citations", {"7": {}})))
    session = cast(dict[str, object], block.setdefault("7", {}))
    for key in keys:
        evidence[key] = True
        body = dict(citations[key])
        body["merge_commit"] = merge
        session[key] = body
    current["evidence_citations"] = block
    state_path = anchor.repo / "docs/control/IMPLEMENTATION_STATE.json"
    candidate = anchor.tmp_path / f"candidate-{stamp.replace(':', '')}.json"
    on_disk = cast(dict[str, object], json.loads(state_path.read_text(encoding="utf-8")))
    if on_disk != state:
        state_path.write_text(
            json.dumps(state, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    write_state(candidate, current)
    apply_record_evidence_transition(state_path, candidate)
    return current


def _g7(repo: Path, *, state_name: str = "TESTED", locator: str | None = None) -> str:
    locators = {
        agent: locator or f"docs/evidence/s07/commissioning/{agent}.json"
        for agent in ("A07", "A08", "A09")
    }
    for agent, path in locators.items():
        if locator != "":
            _write_json(repo / path, {"agent": agent})
    digest = _write_json(
        repo / "docs/evidence/s07/commissioning/g7-record.json",
        {
            "agents": ["A07", "A08", "A09"],
            "state": state_name,
            "g7_go_record_sha256": DIGEST,
            "approved_at": "2026-10-10T12:00:00Z",
        },
    )
    loaded = yaml.safe_load((repo / "config/agents.yaml").read_text(encoding="utf-8"))
    document = cast(dict[str, object], loaded)
    rows = cast(list[dict[str, object]], document["agents"])
    for row in rows:
        if row.get("agent_id") in {"A07", "A08", "A09"}:
            row["commissioning_state"] = state_name
            row["commissioning_evidence"] = [locators[cast(str, row["agent_id"])]]
    (repo / "config/agents.yaml").write_text(yaml.safe_dump(document), encoding="utf-8")
    return digest


def _close(anchor: Anchor, state: ControlState, commit_c: str, g7_digest: str) -> ControlState:
    current = _advance(state, "2026-10-10T18:00:00Z")
    _evidence(current)[CLOSURE_KEY] = True
    current["head_sha"] = commit_c
    current["evidence_closure_commit_sha"] = commit_c
    cited = cast(dict[str, object], _citations(current)["7"])
    cited[CLOSURE_KEY] = {
        "closure_commit": commit_c,
        "recorded_at": "2026-10-10T18:00:00Z",
        "g7_record_blob_sha256": g7_digest,
    }
    state_path = anchor.repo / "docs/control/IMPLEMENTATION_STATE.json"
    candidate = anchor.tmp_path / "closure.json"
    write_state(candidate, current)
    apply_record_closure_transition(state_path, candidate)
    return current


def _record_through_eleven(
    anchor: Anchor, *, g7_state: str = "TESTED"
) -> tuple[ControlState, str, str]:
    qa_path = anchor.repo / "docs/evidence/s07/product_qa_implemented/p4_qa.json"
    planted_qa = _plant(anchor.repo, ("product_qa_implemented",))
    qa_sha = _sha256(qa_path.read_bytes())
    keys = tuple(key for key in NON_CLOSURE_KEYS if key != "product_qa_implemented")
    planted = _plant(anchor.repo, keys, qa_sha=qa_sha)
    planted.update(planted_qa)
    g7_digest = _g7(anchor.repo, state_name=g7_state)
    merge = _commit(anchor.repo, "test: session 07 evidence blobs")
    first = _apply_record(
        anchor,
        anchor.state,
        tuple(key for key in NON_CLOSURE_KEYS if key != KEY_ELEVEN),
        planted,
        merge,
        "2026-10-10T13:00:00Z",
    )
    _commit(anchor.repo, "test: record keys 1-10")
    second = _apply_record(
        anchor,
        first,
        (KEY_ELEVEN,),
        planted,
        merge,
        "2026-10-10T14:00:00Z",
    )
    commit_c = _commit(anchor.repo, "test: record key 11")
    return second, commit_c, g7_digest


def test_11_readme_is_not_proof(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    key = KEY_TWO
    readme = {
        "mode": "execute",
        "redaction_self_check": "PASS",
        "space_id": SANDBOX_SPACE_ID,
        "parent_page_id": SANDBOX_PARENT_PAGE_ID,
    }
    qa = _run_document("p4_qa")
    readme_path = f"docs/evidence/s07/{key}/README.md"
    qa_path = f"docs/evidence/s07/{key}/p4_qa.json"
    manifest = {
        "session": 7,
        "key": key,
        "phase": "p0",
        "artifacts": [
            {
                "kind": "p2_build_exec",
                "path": readme_path,
                "sha256": _write_json(anchor.repo / readme_path, readme),
            },
            {"kind": "p4_qa", "path": qa_path, "sha256": _write_json(anchor.repo / qa_path, qa)},
        ],
        "reviewer_pass": "pass",
        "verifier_pass": "pass",
        "go_record_sha256": None,
    }
    digest = _write_json(anchor.repo / f"docs/evidence/s07/{key}/manifest.json", manifest)
    merge = _commit(anchor.repo, "test: readme artifact")
    with pytest.raises(ControlStateError, match="artifact path or kind"):
        _apply_record(
            anchor,
            anchor.state,
            (key,),
            {key: _citation(key, digest=digest)},
            merge,
            "2026-10-10T13:00:00Z",
        )


def test_12_and_13_manifest_key_and_session_must_match(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    citations = _plant(anchor.repo, (KEY_TWO,))
    manifest_path = anchor.repo / f"docs/evidence/s07/{KEY_TWO}/manifest.json"
    manifest = cast(dict[str, object], json.loads(manifest_path.read_text(encoding="utf-8")))
    manifest["key"] = KEY_THREE
    digest = _write_json(manifest_path, manifest)
    merge = _commit(anchor.repo, "test: wrong manifest key")
    body = dict(citations[KEY_TWO])
    body["manifest_blob_sha256"] = digest
    with pytest.raises(ControlStateError, match="must declare session 7 and that key"):
        _apply_record(
            anchor, anchor.state, (KEY_TWO,), {KEY_TWO: body}, merge, "2026-10-10T13:00:00Z"
        )

    session_root = tmp_path / "session"
    session_root.mkdir()
    session_anchor = _anchor(session_root)
    again = _plant(session_anchor.repo, (KEY_TWO,))
    path = session_anchor.repo / f"docs/evidence/s07/{KEY_TWO}/manifest.json"
    document = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
    document["session"] = 6
    session_digest = _write_json(path, document)
    session_merge = _commit(session_anchor.repo, "test: session 6 manifest")
    session_body = dict(again[KEY_TWO])
    session_body["manifest_blob_sha256"] = session_digest
    with pytest.raises(ControlStateError, match="must declare session 7 and that key"):
        _apply_record(
            session_anchor,
            session_anchor.state,
            (KEY_TWO,),
            {KEY_TWO: session_body},
            session_merge,
            "2026-10-10T13:01:00Z",
        )


def test_14_merge_commit_must_descend_from_the_session_07_tip(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    citations = _plant(anchor.repo, (KEY_ONE,))
    merge = _commit(anchor.repo, "test: evidence present")
    del merge
    with pytest.raises(ControlStateError, match="must descend from the session 07 close tip"):
        _apply_record(
            anchor,
            anchor.state,
            (KEY_ONE,),
            citations,
            BOOTSTRAP,
            "2026-10-10T13:00:00Z",
        )


def test_15_evidence_must_exist_at_merge_commit_not_only_at_head(tmp_path: Path) -> None:
    """The cited commit is the fixture commit, which has no Session 07 evidence tree."""
    anchor = _anchor(tmp_path)
    citations = _plant(anchor.repo, (KEY_ONE,))
    _commit(anchor.repo, "test: evidence added after the cited commit")
    with pytest.raises(ControlStateError, match="evidence blob missing"):
        _apply_record(
            anchor,
            anchor.state,
            (KEY_ONE,),
            citations,
            anchor.sha,
            "2026-10-10T13:00:00Z",
        )


def test_16_blob_sha_is_used_not_the_worktree(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    citations = _plant(anchor.repo, (KEY_ONE,))
    merge = _commit(anchor.repo, "test: blob")
    current = _advance(anchor.state)
    _evidence(current)[KEY_ONE] = True
    body = dict(citations[KEY_ONE])
    body["merge_commit"] = merge
    current["evidence_citations"] = {"7": {KEY_ONE: body}}
    artifact = anchor.repo / f"docs/evidence/s07/{KEY_ONE}/p2_build_exec.json"
    artifact.write_text('{"mode":"worktree"}\n', encoding="utf-8")
    manifest = anchor.repo / f"docs/evidence/s07/{KEY_ONE}/manifest.json"
    manifest.write_bytes(manifest.read_bytes() + b"\n")
    verify_record_evidence_git(anchor.repo, current, head_commit=merge)
    body["manifest_blob_sha256"] = _sha256(manifest.read_bytes())
    with pytest.raises(ControlStateError, match="manifest blob sha256"):
        verify_record_evidence_git(anchor.repo, current, head_commit=merge)


def test_merge_commit_must_be_an_ancestor_of_the_recorded_commit(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    citations = _plant(anchor.repo, (KEY_ONE,))
    side = _commit(anchor.repo, "test: evidence on a side commit")
    _git(anchor.repo, "branch", "evidence-side")
    _git(anchor.repo, "checkout", "-B", BRANCH, anchor.sha)
    current = _advance(anchor.state)
    _evidence(current)[KEY_ONE] = True
    body = dict(citations[KEY_ONE])
    body["merge_commit"] = side
    current["evidence_citations"] = {"7": {KEY_ONE: body}}
    with pytest.raises(ControlStateError, match="ancestor of the recorded commit"):
        verify_record_evidence_git(anchor.repo, current, head_commit=anchor.sha)


def test_artifact_must_live_in_its_own_key_folder(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    citations = _plant(anchor.repo, (KEY_ONE,))
    manifest_path = anchor.repo / f"docs/evidence/s07/{KEY_ONE}/manifest.json"
    manifest = cast(dict[str, object], json.loads(manifest_path.read_text(encoding="utf-8")))
    artifacts = cast(list[dict[str, object]], manifest["artifacts"])
    foreign = f"docs/evidence/s07/{KEY_TWO}/p2_build_exec.json"
    for artifact in artifacts:
        if artifact["kind"] != "p2_build_exec":
            continue
        payload = (anchor.repo / cast(str, artifact["path"])).read_bytes()
        destination = anchor.repo / foreign
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        artifact["path"] = foreign
        artifact["sha256"] = _sha256(payload)
    digest = _write_json(manifest_path, manifest)
    merge = _commit(anchor.repo, "test: artifact outside its key folder")
    body = dict(citations[KEY_ONE])
    body["manifest_blob_sha256"] = digest
    with pytest.raises(ControlStateError, match="artifact path or kind"):
        _apply_record(
            anchor, anchor.state, (KEY_ONE,), {KEY_ONE: body}, merge, "2026-10-10T13:00:00Z"
        )


def test_p5_qa_record_binding_and_p8b_control_digests(tmp_path: Path) -> None:
    ledger_root = tmp_path / "ledger"
    ledger_root.mkdir()
    ledger = _anchor(ledger_root)
    qa = _plant(ledger.repo, ("product_qa_implemented",))

    def _wrong_qa_binding(kind: str, document: dict[str, object]) -> None:
        if kind == "p5_ledger":
            document["qa_record_sha256"] = "ab" * 32

    cited = _plant(
        ledger.repo,
        ("product_fact_ledger_persisted",),
        qa_sha="cd" * 32,
        mutate=_wrong_qa_binding,
    )
    cited.update(qa)
    merge = _commit(ledger.repo, "test: unbound ledger")
    with pytest.raises(ControlStateError, match="qa_record_sha256 must equal the cited p4_qa"):
        _apply_record(
            ledger,
            ledger.state,
            ("product_qa_implemented", "product_fact_ledger_persisted"),
            cited,
            merge,
            "2026-10-10T13:00:00Z",
        )

    control_root = tmp_path / "control"
    control_root.mkdir()
    control = _anchor(control_root)

    def _wrong_control_digest(kind: str, document: dict[str, object]) -> None:
        if kind == "p8b_control_record":
            digests = cast(dict[str, object], document["control_file_sha256"])
            digests["docs/control/DECISIONS.md"] = "c" * 64

    qa_file = control.repo / "docs/evidence/s07/product_qa_implemented/p4_qa.json"
    planted_qa = _plant(control.repo, ("product_qa_implemented",))
    qa_sha = _sha256(qa_file.read_bytes())
    other_keys = tuple(key for key in NON_CLOSURE_KEYS if key != "product_qa_implemented")
    planted = _plant(control.repo, other_keys, qa_sha=qa_sha, mutate=_wrong_control_digest)
    planted.update(planted_qa)
    control_merge = _commit(control.repo, "test: control evidence")
    recorded = _apply_record(
        control,
        control.state,
        tuple(key for key in NON_CLOSURE_KEYS if key != KEY_ELEVEN),
        planted,
        control_merge,
        "2026-10-10T13:00:00Z",
    )
    _commit(control.repo, "test: record keys 1-10")
    with pytest.raises(ControlStateError, match="digest does not match"):
        _apply_record(
            control,
            recorded,
            (KEY_ELEVEN,),
            planted,
            control_merge,
            "2026-10-10T14:00:00Z",
        )


def test_17_disallowed_kind_is_refused(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    citations = _plant(anchor.repo, (KEY_TWO,))
    manifest_path = anchor.repo / f"docs/evidence/s07/{KEY_TWO}/manifest.json"
    manifest = cast(dict[str, object], json.loads(manifest_path.read_text(encoding="utf-8")))
    artifacts = cast(list[dict[str, object]], manifest["artifacts"])
    for artifact in artifacts:
        if artifact["kind"] == "p2_build_exec":
            artifact["kind"] = "p6_test_record"
            path = anchor.repo / cast(str, artifact["path"])
            path.write_bytes(
                (
                    json.dumps(
                        {
                            "mode": "execute",
                            "redaction_self_check": "PASS",
                            "space_id": SANDBOX_SPACE_ID,
                            "parent_page_id": SANDBOX_PARENT_PAGE_ID,
                            "test_node_ids": ["tests/bootstrap/test_s07_evidence_record.py"],
                            "ci_run": "ci-test",
                        },
                        indent=2,
                    )
                    + "\n"
                ).encode()
            )
            artifact["sha256"] = _sha256(path.read_bytes())
    digest = _write_json(manifest_path, manifest)
    merge = _commit(anchor.repo, "test: disallowed kind")
    body = dict(citations[KEY_TWO])
    body["manifest_blob_sha256"] = digest
    with pytest.raises(ControlStateError, match="artifact kinds"):
        _apply_record(
            anchor, anchor.state, (KEY_TWO,), {KEY_TWO: body}, merge, "2026-10-10T13:00:00Z"
        )


def test_18_qa_must_pass_and_mode_must_be_execute(tmp_path: Path) -> None:
    def _refuse(
        mutator: Callable[[str, dict[str, object]], None], fragment: str, folder: str
    ) -> None:
        anchor = _anchor(tmp_path / folder)
        anchor.tmp_path = tmp_path / folder
        citations = _plant(anchor.repo, (KEY_ONE,), mutate=mutator)
        merge = _commit(anchor.repo, "test: bad run evidence")
        with pytest.raises(ControlStateError, match=fragment):
            _apply_record(
                anchor,
                anchor.state,
                (KEY_ONE,),
                citations,
                merge,
                "2026-10-10T13:00:00Z",
            )

    def _not_run(kind: str, document: dict[str, object]) -> None:
        if kind == "p4_qa":
            document["qa_verdict"] = "NOT_RUN"

    def _dry_run(kind: str, document: dict[str, object]) -> None:
        if kind == "p2_build_exec":
            document["mode"] = "dry-run"

    def _wrong_parent(kind: str, document: dict[str, object]) -> None:
        if kind == "p2_build_exec":
            document["parent_page_id"] = "not-the-sandbox-parent"

    _refuse(_not_run, "qa_verdict must be PASS", "qa")
    _refuse(_dry_run, "mode must be execute", "mode")
    _refuse(_wrong_parent, "parent must be the sandbox parent", "parent")


def test_21_closure_commit_must_contain_the_pre_transition_state(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    previous = _eleven(anchor.state)
    current = _advance(previous, "2026-10-10T18:00:00Z")
    _evidence(current)[CLOSURE_KEY] = True
    current["head_sha"] = anchor.sha
    current["evidence_closure_commit_sha"] = anchor.sha
    cited = cast(dict[str, object], _citations(current)["7"])
    cited[CLOSURE_KEY] = _closure_citation(anchor.sha)
    with pytest.raises(ControlStateError, match=re.escape(CLOSURE_STATE_MISMATCH)):
        verify_record_closure_git(
            anchor.repo,
            previous,
            current,
            writing_commit=anchor.sha,
            runtime=False,
        )


def test_22_closure_commit_must_not_name_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    anchor = _anchor(tmp_path)
    previous = _eleven(anchor.state)
    current = _advance(previous, "2026-10-10T18:00:00Z")
    _evidence(current)[CLOSURE_KEY] = True
    current["head_sha"] = anchor.sha
    current["evidence_closure_commit_sha"] = anchor.sha
    cited = cast(dict[str, object], _citations(current)["7"])
    cited[CLOSURE_KEY] = _closure_citation(anchor.sha)

    def _names_itself(repo_root: Path, commit: str) -> dict[str, object]:
        del repo_root
        document = cast(dict[str, object], copy.deepcopy(previous))
        document["head_sha"] = commit
        return document

    monkeypatch.setattr(
        "money_machine.control.s07_evidence._state_document_at",
        _names_itself,
    )
    with pytest.raises(ControlStateError, match=re.escape(CLOSURE_NAMES_ITSELF)):
        verify_record_closure_git(
            anchor.repo,
            previous,
            current,
            writing_commit=anchor.sha,
            runtime=False,
        )


def test_25_session_07_tip_must_be_an_ancestor_of_the_closure_commit(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    previous = _eleven(anchor.state)
    write_state(anchor.repo / "docs/control/IMPLEMENTATION_STATE.json", previous)
    _commit(anchor.repo, "test: eleven true")
    tree = _git(anchor.repo, "rev-parse", "HEAD^{tree}").strip()
    orphan = _git(anchor.repo, "commit-tree", tree, "-m", "orphan")
    orphan = orphan.strip()
    current = _advance(previous, "2026-10-10T18:00:00Z")
    _evidence(current)[CLOSURE_KEY] = True
    current["head_sha"] = orphan
    current["evidence_closure_commit_sha"] = orphan
    cited = cast(dict[str, object], _citations(current)["7"])
    cited[CLOSURE_KEY] = _closure_citation(orphan)
    with pytest.raises(ControlStateError, match="must be an ancestor of the closure commit"):
        verify_record_closure_git(
            anchor.repo,
            previous,
            current,
            writing_commit=anchor.sha,
            runtime=False,
        )


def test_26_closure_requires_head_equal_to_c_and_a_clean_tree(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    state, commit_c, g7_digest = _record_through_eleven(anchor)
    closed = _close(anchor, state, commit_c, g7_digest)
    assert closed["head_sha"] == commit_c
    assert closed["evidence_closure_commit_sha"] == commit_c
    _git(anchor.repo, "checkout", "--", "docs/control/IMPLEMENTATION_STATE.json")
    _git(anchor.repo, "commit", "--allow-empty", "-m", "test: move head past closure")
    candidate = anchor.tmp_path / "again.json"
    write_state(anchor.repo / "docs/control/IMPLEMENTATION_STATE.json", state)
    moved = _advance(state, "2026-10-10T18:01:00Z")
    _evidence(moved)[CLOSURE_KEY] = True
    moved["head_sha"] = commit_c
    moved["evidence_closure_commit_sha"] = commit_c
    cited = cast(dict[str, object], _citations(moved)["7"])
    cited[CLOSURE_KEY] = _closure_citation(commit_c)
    cited_body = cast(dict[str, object], cited[CLOSURE_KEY])
    cited_body["g7_record_blob_sha256"] = g7_digest
    write_state(candidate, moved)
    with pytest.raises(ControlStateError, match="HEAD must equal the evidence-closure commit"):
        apply_record_closure_transition(
            anchor.repo / "docs/control/IMPLEMENTATION_STATE.json",
            candidate,
        )
    _git(anchor.repo, "reset", "--hard", commit_c)
    (anchor.repo / "evidence.txt").write_text("dirty\n", encoding="utf-8")
    _git(anchor.repo, "add", "evidence.txt")
    with pytest.raises(ControlStateError, match="must be clean"):
        apply_record_closure_transition(
            anchor.repo / "docs/control/IMPLEMENTATION_STATE.json",
            candidate,
        )


def test_30_and_42_g7_must_match_agents_and_resolve(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    state, commit_c, g7_digest = _record_through_eleven(anchor, g7_state="DESIGNED")
    with pytest.raises(ControlStateError, match="TESTED or COMMISSIONED"):
        _close(anchor, state, commit_c, g7_digest)

    missing_root = tmp_path / "missing"
    missing_root.mkdir()
    missing = _anchor(missing_root)
    missing_state, _missing_c, _digest = _record_through_eleven(missing)
    _git(missing.repo, "rm", "docs/evidence/s07/commissioning/g7-record.json")
    removed = _commit(missing.repo, "test: drop g7")
    with pytest.raises(ControlStateError, match="evidence blob missing"):
        _close(missing, missing_state, removed, _digest)

    mismatch_root = tmp_path / "mismatch"
    mismatch_root.mkdir()
    mismatch = _anchor(mismatch_root)
    mismatch_state, _mismatch_c, mismatch_digest = _record_through_eleven(mismatch)
    loaded = yaml.safe_load((mismatch.repo / "config/agents.yaml").read_text(encoding="utf-8"))
    rows = cast(list[dict[str, object]], cast(dict[str, object], loaded)["agents"])
    for row in rows:
        if row.get("agent_id") == "A07":
            row["commissioning_state"] = "DESIGNED"
    (mismatch.repo / "config/agents.yaml").write_text(yaml.safe_dump(loaded), encoding="utf-8")
    drifted = _commit(mismatch.repo, "test: agents drift")
    with pytest.raises(ControlStateError, match="not at the g7 commissioning state"):
        verify_record_closure_git(
            mismatch.repo,
            mismatch_state,
            _closure_candidate(mismatch_state, drifted, mismatch_digest),
            writing_commit=drifted,
            runtime=False,
        )

    dangling_root = tmp_path / "dangling"
    dangling_root.mkdir()
    dangling = _anchor(dangling_root)
    dangling_state, _dangling_c, dangling_digest = _record_through_eleven(dangling)
    loaded = yaml.safe_load((dangling.repo / "config/agents.yaml").read_text(encoding="utf-8"))
    rows = cast(list[dict[str, object]], cast(dict[str, object], loaded)["agents"])
    for row in rows:
        if row.get("agent_id") == "A09":
            row["commissioning_evidence"] = ["docs/evidence/s07/commissioning/missing.json"]
    (dangling.repo / "config/agents.yaml").write_text(yaml.safe_dump(loaded), encoding="utf-8")
    dangling_commit = _commit(dangling.repo, "test: missing locator")
    with pytest.raises(ControlStateError, match="evidence blob missing"):
        verify_record_closure_git(
            dangling.repo,
            dangling_state,
            _closure_candidate(dangling_state, dangling_commit, dangling_digest),
            writing_commit=dangling_commit,
            runtime=False,
        )

    readme_root = tmp_path / "readme-locator"
    readme_root.mkdir()
    readme = _anchor(readme_root)
    readme_state, _readme_c, readme_digest = _record_through_eleven(readme)
    loaded = yaml.safe_load((readme.repo / "config/agents.yaml").read_text(encoding="utf-8"))
    rows = cast(list[dict[str, object]], cast(dict[str, object], loaded)["agents"])
    for row in rows:
        if row.get("agent_id") in {"A07", "A08", "A09"}:
            row["commissioning_evidence"] = ["README.md"]
    (readme.repo / "config/agents.yaml").write_text(yaml.safe_dump(loaded), encoding="utf-8")
    readme_commit = _commit(readme.repo, "test: readme locator")
    with pytest.raises(ControlStateError, match="commissioning manifest"):
        verify_record_closure_git(
            readme.repo,
            readme_state,
            _closure_candidate(readme_state, readme_commit, readme_digest),
            writing_commit=readme_commit,
            runtime=False,
        )


def _closure_candidate(state: ControlState, commit_c: str, g7_digest: str) -> ControlState:
    current = _advance(state, "2026-10-10T18:00:00Z")
    _evidence(current)[CLOSURE_KEY] = True
    current["head_sha"] = commit_c
    current["evidence_closure_commit_sha"] = commit_c
    cited = cast(dict[str, object], _citations(current)["7"])
    cited[CLOSURE_KEY] = {
        "closure_commit": commit_c,
        "recorded_at": "2026-10-10T18:00:00Z",
        "g7_record_blob_sha256": g7_digest,
    }
    return current


def test_33_and_34_replay_refuses_bad_history_and_keeps_first_parent(
    tmp_path: Path,
) -> None:
    anchor = _anchor(tmp_path)
    replay_state_history(anchor.repo, anchor.sha)
    citations = _plant(anchor.repo, (KEY_ONE,))
    merge = _commit(anchor.repo, "test: key one evidence")
    recorded = _apply_record(
        anchor,
        anchor.state,
        (KEY_ONE,),
        citations,
        merge,
        "2026-10-10T13:00:00Z",
    )
    _commit(anchor.repo, "test: record key one")
    hand = copy.deepcopy(recorded)
    hand["state_revision"] = recorded["state_revision"] + 1
    hand["updated_at"] = "2026-10-10T13:30:00Z"
    for key in (*NON_CLOSURE_KEYS, CLOSURE_KEY):
        _evidence(hand)[key] = True
    hand["evidence_citations"] = {
        "7": {key: _citation(key, merge=merge) for key in (*NON_CLOSURE_KEYS, CLOSURE_KEY)}
    }
    write_state(anchor.repo / "docs/control/IMPLEMENTATION_STATE.json", hand)
    _commit(anchor.repo, "test: hand edit")
    with pytest.raises(ControlStateError, match="replay refused"):
        replay_state_history(anchor.repo, anchor.sha)

    revert_root = _anchor(tmp_path / "revert")
    revert_root.tmp_path = tmp_path / "revert"
    revert_citations = _plant(revert_root.repo, (KEY_ONE,))
    revert_merge = _commit(revert_root.repo, "test: evidence")
    revert_state = _apply_record(
        revert_root,
        revert_root.state,
        (KEY_ONE,),
        revert_citations,
        revert_merge,
        "2026-10-10T13:00:00Z",
    )
    _commit(revert_root.repo, "test: record")
    write_state(revert_root.repo / "docs/control/IMPLEMENTATION_STATE.json", revert_root.state)
    _commit(revert_root.repo, "test: hand revert")
    del revert_state
    with pytest.raises(ControlStateError, match="replay refused"):
        replay_state_history(revert_root.repo, revert_root.sha)

    gap = _anchor(tmp_path / "gap")
    gap.tmp_path = tmp_path / "gap"
    gap_citations = _plant(gap.repo, (KEY_ONE,))
    gap_merge = _commit(gap.repo, "test: evidence")
    jumped = _advance(gap.state, "2026-10-10T13:00:00Z")
    jumped["state_revision"] = gap.state["state_revision"] + 2
    _evidence(jumped)[KEY_ONE] = True
    body = dict(gap_citations[KEY_ONE])
    body["merge_commit"] = gap_merge
    jumped["evidence_citations"] = {"7": {KEY_ONE: body}}
    write_state(gap.repo / "docs/control/IMPLEMENTATION_STATE.json", jumped)
    _commit(gap.repo, "test: revision gap")
    with pytest.raises(ControlStateError, match="replay refused"):
        replay_state_history(gap.repo, gap.sha)

    mixed = _anchor(tmp_path / "mixed")
    mixed.tmp_path = tmp_path / "mixed"
    mixed_citations = _plant(mixed.repo, (KEY_ONE,))
    mixed_merge = _commit(mixed.repo, "test: evidence")
    squashed = _advance(mixed.state)
    _evidence(squashed)[KEY_ONE] = True
    squashed["head_sha"] = NEW_COMMIT
    mixed_body = dict(mixed_citations[KEY_ONE])
    mixed_body["merge_commit"] = mixed_merge
    squashed["evidence_citations"] = {"7": {KEY_ONE: mixed_body}}
    write_state(mixed.repo / "docs/control/IMPLEMENTATION_STATE.json", squashed)
    _commit(mixed.repo, "test: two steps in one commit")
    with pytest.raises(ControlStateError, match="replay refused"):
        replay_state_history(mixed.repo, mixed.sha)

    dirty = _anchor(tmp_path / "dirty")
    state_path = dirty.repo / "docs/control/IMPLEMENTATION_STATE.json"
    original = state_path.read_bytes()
    state_path.write_text(original.decode() + "\n", encoding="utf-8")
    with pytest.raises(ControlStateError, match=re.escape(WORKTREE_MISMATCH)):
        replay_state_history(dirty.repo, dirty.sha)
    state_path.write_bytes(original)

    drifted = _anchor(tmp_path / "drift")
    drifted_state = copy.deepcopy(drifted.state)
    notes = cast(dict[str, object], drifted_state["notes"])
    notes["changed"] = True
    write_state(drifted.repo / "docs/control/IMPLEMENTATION_STATE.json", drifted_state)
    drifted_sha = _commit(drifted.repo, "test: anchor drift")
    with pytest.raises(ControlStateError, match="rev-64 fixture"):
        replay_state_history(drifted.repo, drifted_sha)

    merge_repo = _anchor(tmp_path / "merge")
    _git(merge_repo.repo, "checkout", "-b", "side")
    side = copy.deepcopy(merge_repo.state)
    side["updated_at"] = "2026-10-10T19:00:00Z"
    write_state(merge_repo.repo / "docs/control/IMPLEMENTATION_STATE.json", side)
    _commit(merge_repo.repo, "test: side state")
    _git(merge_repo.repo, "checkout", BRANCH)
    _git(merge_repo.repo, "merge", "--no-ff", "--no-commit", "side")
    write_state(merge_repo.repo / "docs/control/IMPLEMENTATION_STATE.json", side)
    _git(merge_repo.repo, "add", "docs/control/IMPLEMENTATION_STATE.json")
    _git(merge_repo.repo, "commit", "-m", "test: merge state")
    with pytest.raises(ControlStateError, match="squash-merged"):
        replay_state_history(merge_repo.repo, merge_repo.sha)

    ours = _anchor(tmp_path / "ours")
    _git(ours.repo, "checkout", "-b", "ignored")
    ignored = copy.deepcopy(ours.state)
    ignored["updated_at"] = "2026-10-10T19:30:00Z"
    write_state(ours.repo / "docs/control/IMPLEMENTATION_STATE.json", ignored)
    _commit(ours.repo, "test: ignored side state")
    _git(ours.repo, "checkout", BRANCH)
    _git(ours.repo, "merge", "-s", "ours", "ignored", "-m", "test: ours merge")
    replay_state_history(ours.repo, ours.sha)


def _flip_sha(digest: str) -> str:
    first = "0" if digest[0] != "0" else "1"
    return first + digest[1:]


def _activation_candidate(state: ControlState, stamp: str) -> ControlState:
    current = _advance(state, stamp)
    current["session_status"] = "incomplete"
    current["current_session"] = 8
    current["required_completion_evidence"] = dict.fromkeys(SESSION_08_EVIDENCE_KEYS, False)
    return current


def _commit_state(anchor: Anchor, state: ControlState, message: str) -> str:
    write_state(anchor.repo / "docs/control/IMPLEMENTATION_STATE.json", state)
    return _commit(anchor.repo, message)


def test_pull_request_head_replays_and_the_merge_ref_does_not(tmp_path: Path) -> None:
    """A state-touching pull request passes at its head and fails on the two-parent merge ref."""
    anchor = _anchor(tmp_path)
    citations = _plant(anchor.repo, (KEY_ONE,))
    merge = _commit(anchor.repo, "test: evidence")
    _apply_record(anchor, anchor.state, (KEY_ONE,), citations, merge, "2026-10-10T13:00:00Z")
    _commit(anchor.repo, "test: record key one")
    _git(anchor.repo, "branch", "pr-head")
    replay_state_history(anchor.repo, anchor.sha)
    _git(anchor.repo, "checkout", "-B", BRANCH, anchor.sha)
    _git(anchor.repo, "merge", "--no-ff", "pr-head", "-m", "test: pull request merge ref")
    with pytest.raises(ControlStateError, match="squash-merged"):
        replay_state_history(anchor.repo, anchor.sha)
    _git(anchor.repo, "checkout", "--detach", "pr-head")
    replay_state_history(anchor.repo, anchor.sha)


def test_48_one_state_commit_passes_pull_request_ci_and_two_fail(tmp_path: Path) -> None:
    """A second state commit fails before merge. One state commit, and zero, pass."""
    one = _anchor(tmp_path / "one")
    (one.repo / "note.txt").write_text("not state\n", encoding="utf-8")
    _commit(one.repo, "test: not state")
    stepped = copy.deepcopy(one.state)
    stepped["updated_at"] = "2026-10-10T13:00:00Z"
    _commit_state(one, stepped, "test: one state step")
    assert_pull_request_state_transitions(one.repo, one.sha)

    none = _anchor(tmp_path / "none")
    (none.repo / "note.txt").write_text("not state\n", encoding="utf-8")
    _commit(none.repo, "test: not state")
    assert_pull_request_state_transitions(none.repo, none.sha)

    two = _anchor(tmp_path / "two")
    first = copy.deepcopy(two.state)
    first["updated_at"] = "2026-10-10T13:00:00Z"
    _commit_state(two, first, "test: first state step")
    second = copy.deepcopy(first)
    second["updated_at"] = "2026-10-10T14:00:00Z"
    _commit_state(two, second, "test: second state step")
    with pytest.raises(ControlStateError, match=f"^{re.escape(ONE_STATE_TRANSITION)}$"):
        assert_pull_request_state_transitions(two.repo, two.sha)


def test_49_pull_request_base_must_be_an_ancestor_of_head(tmp_path: Path) -> None:
    """A stale or missing base fails the pull-request run and names rebase, not merge."""
    anchor = _anchor(tmp_path)
    _git(anchor.repo, "checkout", "-b", "pr")
    changed = copy.deepcopy(anchor.state)
    changed["updated_at"] = "2026-10-10T16:00:00Z"
    head = _commit_state(anchor, changed, "test: pr state step")
    _git(anchor.repo, "checkout", BRANCH)
    moved = copy.deepcopy(anchor.state)
    moved["updated_at"] = "2026-10-10T15:00:00Z"
    write_state(anchor.repo / "docs/control/IMPLEMENTATION_STATE.json", moved)
    new_base = _commit(anchor.repo, "test: base moved").strip()
    _git(anchor.repo, "checkout", "--detach", head)
    with pytest.raises(ControlStateError, match=f"^{re.escape(REBASE_NOT_MERGE)}$"):
        assert_pull_request_state_transitions(anchor.repo, new_base)
    with pytest.raises(ControlStateError, match=f"^{re.escape(REBASE_NOT_MERGE)}$"):
        assert_pull_request_state_transitions(anchor.repo, "a" * 40)
    assert_pull_request_state_transitions(anchor.repo, anchor.sha)


def test_34_replay_rechecks_record_closure_and_revoke(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deleting a replay git re-check accepts a step the stock replay refuses."""
    bad_root = tmp_path / "bad-hash"
    bad_root.mkdir()
    bad = _anchor(bad_root)
    qa_file = bad.repo / "docs/evidence/s07/product_qa_implemented/p4_qa.json"
    planted_qa = _plant(bad.repo, ("product_qa_implemented",))
    qa_sha = _sha256(qa_file.read_bytes())
    other = tuple(key for key in NON_CLOSURE_KEYS if key != "product_qa_implemented")
    planted = _plant(bad.repo, other, qa_sha=qa_sha)
    planted.update(planted_qa)
    g7_digest = _g7(bad.repo)
    merge = _commit(bad.repo, "test: evidence blobs")
    wrong = _advance(bad.state, "2026-10-10T13:00:00Z")
    _evidence(wrong)[KEY_ONE] = True
    cited = dict(planted[KEY_ONE])
    cited["merge_commit"] = merge
    cited["manifest_blob_sha256"] = _flip_sha(cast(str, cited["manifest_blob_sha256"]))
    wrong["evidence_citations"] = {"7": {KEY_ONE: cited}}
    _commit_state(bad, wrong, "test: record with a wrong manifest hash")
    revoked = _advance(wrong, "2026-10-10T13:10:00Z")
    _evidence(revoked)[KEY_ONE] = False
    revoked["evidence_citations"] = {
        "7": {},
        "7_revoked": [
            {
                "key": KEY_ONE,
                "reason": "manifest hash did not match the blob",
                "revoked_at": "2026-10-10T13:10:00Z",
                "revoked_in_rev": revoked["state_revision"],
            }
        ],
    }
    _commit_state(bad, revoked, "test: revoke the bad record")
    recorded = _apply_record(
        bad,
        revoked,
        tuple(key for key in NON_CLOSURE_KEYS if key != KEY_ELEVEN),
        planted,
        merge,
        "2026-10-10T13:20:00Z",
    )
    _commit(bad.repo, "test: record keys 1-10")
    eleven = _apply_record(bad, recorded, (KEY_ELEVEN,), planted, merge, "2026-10-10T14:00:00Z")
    commit_c = _commit(bad.repo, "test: record key 11")
    closed = _close(bad, eleven, commit_c, g7_digest)
    _commit(bad.repo, "test: closure")
    candidate = bad.tmp_path / "activate-bad-hash.json"
    write_state(candidate, _activation_candidate(closed, "2026-10-10T18:30:00Z"))
    with pytest.raises(ControlStateError, match="replay refused"):
        _apply_activation_transition(
            bad.repo / "docs/control/IMPLEMENTATION_STATE.json",
            candidate,
            replay_anchor=bad.sha,
        )

    g7_root = tmp_path / "bad-g7"
    g7_root.mkdir()
    g7_anchor = _anchor(g7_root)
    state, commit_c, digest = _record_through_eleven(g7_anchor)
    bad_closure = _closure_candidate(state, commit_c, _flip_sha(digest))
    _commit_state(g7_anchor, bad_closure, "test: closure with a bad g7 hash")
    g7_candidate = g7_anchor.tmp_path / "activate-bad-g7.json"
    write_state(g7_candidate, _activation_candidate(bad_closure, "2026-10-10T18:40:00Z"))
    with pytest.raises(ControlStateError, match="replay refused"):
        _apply_activation_transition(
            g7_anchor.repo / "docs/control/IMPLEMENTATION_STATE.json",
            g7_candidate,
            replay_anchor=g7_anchor.sha,
        )

    calls: list[str] = []
    real_revoke = verify_revoke_evidence_git

    def _spy(repo_root: Path, current: ControlState, *, head_commit: str) -> None:
        calls.append(head_commit)
        real_revoke(repo_root, current, head_commit=head_commit)

    monkeypatch.setattr(
        "money_machine.control.s07_evidence.verify_revoke_evidence_git",
        _spy,
    )
    revoke_root = tmp_path / "revoke-recheck"
    revoke_root.mkdir()
    revoke_anchor = _anchor(revoke_root)
    pair = _plant(revoke_anchor.repo, (KEY_ONE, KEY_TWO))
    pair_merge = _commit(revoke_anchor.repo, "test: two keys")
    both = _apply_record(
        revoke_anchor,
        revoke_anchor.state,
        (KEY_ONE, KEY_TWO),
        pair,
        pair_merge,
        "2026-10-10T13:00:00Z",
    )
    _commit(revoke_anchor.repo, "test: record two keys")
    dropped = _advance(both, "2026-10-10T13:30:00Z")
    _evidence(dropped)[KEY_TWO] = False
    block = cast(dict[str, object], copy.deepcopy(dropped["evidence_citations"]))
    session = cast(dict[str, object], block["7"])
    del session[KEY_TWO]
    block["7_revoked"] = [
        {
            "key": KEY_TWO,
            "reason": "second key was recorded against the wrong parent",
            "revoked_at": "2026-10-10T13:30:00Z",
            "revoked_in_rev": dropped["state_revision"],
        }
    ]
    dropped["evidence_citations"] = block
    _commit_state(revoke_anchor, dropped, "test: revoke key two")
    replay_state_history(revoke_anchor.repo, revoke_anchor.sha)
    assert calls

    kept = dict(cast(dict[str, object], session[KEY_ONE]))
    kept["manifest_blob_sha256"] = _flip_sha(cast(str, kept["manifest_blob_sha256"]))
    session[KEY_ONE] = kept
    with pytest.raises(ControlStateError, match="manifest blob sha256"):
        verify_revoke_evidence_git(
            revoke_anchor.repo,
            dropped,
            head_commit=_git(revoke_anchor.repo, "rev-parse", "HEAD").strip(),
        )


def test_35_pin_helper_mutants_die() -> None:
    tip = cast(Mapping[str, object], _fresh())
    assert_session_seven_tip(tip)
    source = __import__("inspect").getsource(assert_session_seven_tip)
    any_source = source.replace(
        "if not all(key in cited for key in true_keys):",
        "if not any(key in cited for key in true_keys):",
        1,
    )
    assert any_source != source
    namespace = dict(assert_session_seven_tip.__globals__)
    exec("from __future__ import annotations\n" + any_source, namespace)
    any_mutant = cast(Callable[[Mapping[str, object]], None], namespace["assert_session_seven_tip"])
    with pytest.raises(ControlStateError, match="must be cited"):
        any_mutant(tip)

    two = _eleven()
    _evidence(two)[KEY_TWO] = True
    del cast(dict[str, object], _citations(two)["7"])[KEY_TWO]
    with pytest.raises(ControlStateError, match="must be cited"):
        assert_session_seven_tip(two)
    any_mutant(cast(Mapping[str, object], two))

    cited = _eleven()
    assert_session_seven_tip(cited)
    needle = 'session_citations = cast(dict[object, object], citations).get("7")'
    blind = source.replace(needle, "session_citations = {}", 1)
    assert blind != source
    blind_namespace = dict(assert_session_seven_tip.__globals__)
    exec("from __future__ import annotations\n" + blind, blind_namespace)
    blind_mutant = cast(
        Callable[[Mapping[str, object]], None],
        blind_namespace["assert_session_seven_tip"],
    )
    with pytest.raises(ControlStateError, match="must be cited"):
        blind_mutant(cast(Mapping[str, object], cited))

    wrong = _fresh()
    wrong["head_sha"] = NEW_COMMIT
    with pytest.raises(ControlStateError, match=re.escape(PRE_CLOSURE_PINS)):
        assert_session_seven_tip(wrong)
    unpinned = source.replace(
        'head = state.get("head_sha")',
        'return\n    head = state.get("head_sha")',
        1,
    )
    pin_namespace = dict(assert_session_seven_tip.__globals__)
    exec("from __future__ import annotations\n" + unpinned, pin_namespace)
    pin_mutant = cast(
        Callable[[Mapping[str, object]], None], pin_namespace["assert_session_seven_tip"]
    )
    pin_mutant(cast(Mapping[str, object], wrong))

    closed = _eleven()
    _evidence(closed)[CLOSURE_KEY] = True
    closed["head_sha"] = NEW_COMMIT
    closed["evidence_closure_commit_sha"] = NEW_COMMIT
    cast(dict[str, object], _citations(closed)["7"])[CLOSURE_KEY] = _closure_citation(NEW_COMMIT)
    assert_session_seven_tip(closed)
    closed["head_sha"] = OTHER_COMMIT
    with pytest.raises(ControlStateError, match=re.escape(CLOSURE_CITATION_PINS)):
        assert_session_seven_tip(closed)
    assert_session_seven_continuity(ROOT)


def test_36_closure_then_activation_then_session_08_completion(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    state, commit_c, g7_digest = _record_through_eleven(anchor)
    activation = _advance(state, "2026-10-10T15:00:00Z")
    activation["session_status"] = "incomplete"
    activation["current_session"] = 8
    activation["required_completion_evidence"] = dict.fromkeys(SESSION_08_EVIDENCE_KEYS, False)
    early = anchor.tmp_path / "early-activation.json"
    write_state(early, activation)
    with pytest.raises(ControlStateError, match="prior-session evidence"):
        _apply_activation_transition(
            anchor.repo / "docs/control/IMPLEMENTATION_STATE.json",
            early,
            replay_anchor=anchor.sha,
        )
    closed = _close(anchor, state, commit_c, g7_digest)
    _commit(anchor.repo, "test: record closure")
    activated = _advance(closed, "2026-10-10T18:30:00Z")
    activated["session_status"] = "incomplete"
    activated["current_session"] = 8
    activated["required_completion_evidence"] = dict.fromkeys(SESSION_08_EVIDENCE_KEYS, False)
    candidate = anchor.tmp_path / "activation.json"
    write_state(candidate, activated)
    applied = _apply_activation_transition(
        anchor.repo / "docs/control/IMPLEMENTATION_STATE.json",
        candidate,
        replay_anchor=anchor.sha,
    )
    assert applied["current_session"] == 8
    previous = copy.deepcopy(applied)
    previous["required_completion_evidence"] = {
        key: key != "evidence_closure_commit_recorded" for key in SESSION_08_EVIDENCE_KEYS
    }
    completed = _advance(previous, "2026-10-10T19:00:00Z")
    completed["session_status"] = "complete"
    completed["completed_sessions"] = list(range(9))
    completed["next_session"] = 9
    completed["next_prompt"] = SESSION_PROMPTS[9]
    completed_evidence = cast(dict[str, bool], completed["required_completion_evidence"])
    completed_evidence["evidence_closure_commit_recorded"] = True
    completed["evidence_closure_commit_sha"] = OTHER_COMMIT
    completed["head_sha"] = OTHER_COMMIT
    contract = dict(completed["transition_contract"])
    contract["completion_requires_next_session"] = 9
    completed["transition_contract"] = contract
    validate_completion_transition(previous, completed)


def test_38_shallow_clone_activation_is_refused(tmp_path: Path) -> None:
    source = tmp_path / "source"
    dest = tmp_path / "dest"
    source.mkdir()
    (source / "docs/control").mkdir(parents=True)
    subprocess.run(["git", "init", "-b", BRANCH, str(source)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(source), "config", "user.name", "S07 Test"], check=True)
    subprocess.run(
        ["git", "-C", str(source), "config", "user.email", "s07@example.invalid"],
        check=True,
    )
    base = _fresh()
    base["repo_root"] = str(dest)
    base["branch"] = BRANCH
    write_state(source / "docs/control/IMPLEMENTATION_STATE.json", base)
    subprocess.run(["git", "-C", str(source), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-m", "base"], check=True)
    state = copy.deepcopy(base)
    state["required_completion_evidence"] = dict.fromkeys(SESSION_EVIDENCE_KEYS[7], True)
    write_state(source / "docs/control/IMPLEMENTATION_STATE.json", state)
    subprocess.run(["git", "-C", str(source), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(source), "commit", "-m", "all true"], check=True)
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{source}", str(dest)],
        check=True,
        capture_output=True,
    )
    shallow = subprocess.run(
        ["git", "-C", str(dest), "rev-parse", "--is-shallow-repository"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert shallow.stdout.strip() == "true"
    state_path = dest / "docs/control/IMPLEMENTATION_STATE.json"
    original = state_path.read_bytes()
    candidate_state = copy.deepcopy(state)
    candidate_state["state_revision"] = state["state_revision"] + 1
    candidate_state["session_status"] = "incomplete"
    candidate_state["current_session"] = 8
    candidate_state["updated_at"] = "2026-10-10T20:00:00Z"
    candidate_state["required_completion_evidence"] = dict.fromkeys(SESSION_08_EVIDENCE_KEYS, False)
    candidate = tmp_path / "activate.json"
    write_state(candidate, candidate_state)
    result = _run_cli(state_path, candidate, "activate")
    assert result.returncode == 2
    assert "repository is shallow" in result.stderr
    assert state_path.read_bytes() == original
    assert not list(state_path.parent.glob(".IMPLEMENTATION_STATE.json.lock"))
    assert not list(state_path.parent.glob(".IMPLEMENTATION_STATE.json.*.tmp"))


def test_39_missing_anchor_is_refused_even_with_an_env_override(tmp_path: Path) -> None:
    repo = tmp_path / "repository"
    state_path = repo / "docs/control/IMPLEMENTATION_STATE.json"
    state_path.parent.mkdir(parents=True)
    state = _fresh()
    state["repo_root"] = str(repo)
    state["branch"] = BRANCH
    for key in SESSION_EVIDENCE_KEYS[7]:
        _evidence(state)[key] = True
    write_state(state_path, state)
    subprocess.run(["git", "init", "-b", BRANCH, str(repo)], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "S07 Test"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "s07@example.invalid"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-m", "all true"], check=True)
    candidate_state = _advance(state, "2026-10-10T20:00:00Z")
    candidate_state["session_status"] = "incomplete"
    candidate_state["current_session"] = 8
    candidate_state["required_completion_evidence"] = dict.fromkeys(SESSION_08_EVIDENCE_KEYS, False)
    candidate = tmp_path / "activate.json"
    write_state(candidate, candidate_state)
    original = state_path.read_bytes()
    env = os.environ.copy()
    env["MM_REPLAY_ANCHOR"] = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    result = _run_cli(state_path, candidate, "activate", env=env)
    assert result.returncode == 2
    assert "anchor does not resolve" in result.stderr
    assert state_path.read_bytes() == original
    assert not list(state_path.parent.glob(".IMPLEMENTATION_STATE.json.lock"))


def test_40_replay_is_not_invoked_before_session_08(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[object] = []

    def _spy(*args: object, **kwargs: object) -> None:
        calls.append((args, kwargs))

    monkeypatch.setattr("money_machine.control.s07_evidence.replay_state_history", _spy)
    prepared = prepare_completed_session_zero(tmp_path)
    apply_activation_transition(prepared.state_path, prepared.candidate_path)
    previous = cast(ControlState, json.loads(prepared.state_path.read_text(encoding="utf-8")))
    assert previous["next_session"] == 1
    control_state._verify_activation_repository(  # pyright: ignore[reportPrivateUsage]
        prepared.state_path, previous, previous, None
    )
    later = copy.deepcopy(previous)
    later["next_session"] = 2
    control_state._verify_activation_repository(  # pyright: ignore[reportPrivateUsage]
        prepared.state_path, later, previous, None
    )
    assert calls == []


def test_41_revoke_rerecord_and_close_keep_7_revoked(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    state, commit_c, g7_digest = _record_through_eleven(anchor)
    revoked = _advance(state, "2026-10-10T16:00:00Z")
    _evidence(revoked)[KEY_THREE] = False
    block = cast(dict[str, object], copy.deepcopy(revoked["evidence_citations"]))
    session = cast(dict[str, object], block["7"])
    del session[KEY_THREE]
    block["7_revoked"] = [
        {
            "key": KEY_THREE,
            "reason": "dashboard evidence pointed at the wrong parent",
            "revoked_at": "2026-10-10T16:00:00Z",
            "revoked_in_rev": revoked["state_revision"],
        }
    ]
    revoked["evidence_citations"] = block
    state_path = anchor.repo / "docs/control/IMPLEMENTATION_STATE.json"
    revoke_path = anchor.tmp_path / "revoke.json"
    write_state(revoke_path, revoked)
    apply_revoke_evidence_transition(state_path, revoke_path)
    merge = _git(anchor.repo, "rev-parse", "HEAD").strip()
    citation = _citation(KEY_THREE, merge=merge)
    manifest = f"{merge}:docs/evidence/s07/{KEY_THREE}/manifest.json"
    citation["manifest_blob_sha256"] = hashlib.sha256(
        subprocess.run(
            ["git", "-C", str(anchor.repo), "cat-file", "blob", manifest],
            check=True,
            capture_output=True,
        ).stdout
    ).hexdigest()
    again = _advance(revoked, "2026-10-10T16:30:00Z")
    _evidence(again)[KEY_THREE] = True
    again_block = cast(dict[str, object], copy.deepcopy(again["evidence_citations"]))
    cast(dict[str, object], again_block["7"])[KEY_THREE] = citation
    again["evidence_citations"] = again_block
    write_state(state_path, revoked)
    _commit(anchor.repo, "test: revoke key 3")
    rerecord = anchor.tmp_path / "rerecord.json"
    write_state(rerecord, again)
    apply_record_evidence_transition(state_path, rerecord)
    kept = cast(dict[str, object], again["evidence_citations"])["7_revoked"]
    assert json.dumps(kept) == json.dumps(block["7_revoked"])
    _commit(anchor.repo, "test: re-record key 3")
    head = _git(anchor.repo, "rev-parse", "HEAD").strip()
    # Closure commit C must still be the key-11 commit. Re-record moved HEAD, so close
    # against the re-record commit only when that commit's state is the pre-transition
    # state. The revoked-and-restored state is that pre-transition state.
    del commit_c, head
    restored = cast(ControlState, json.loads(state_path.read_text(encoding="utf-8")))
    commit_now = _git(anchor.repo, "rev-parse", "HEAD").strip()
    closed = _close(anchor, restored, commit_now, g7_digest)
    assert closed["evidence_citations"]["7_revoked"] == block["7_revoked"]
    edited = _advance(revoked, "2026-10-10T16:40:00Z")
    _evidence(edited)[KEY_THREE] = True
    edited_block = cast(dict[str, object], copy.deepcopy(edited["evidence_citations"]))
    cast(dict[str, object], edited_block["7"])[KEY_THREE] = _citation(KEY_THREE)
    edited_block["7_revoked"] = []
    edited["evidence_citations"] = edited_block
    _expect("record", revoked, edited, "7_revoked must stay byte-identical")
    closure_previous, closure_current = _valid_closure()
    entry = {
        "key": KEY_THREE,
        "reason": "dashboard evidence pointed at the wrong parent",
        "revoked_at": "2026-10-10T12:00:00Z",
        "revoked_in_rev": 70,
    }
    edited_entry = dict(entry)
    edited_entry["reason"] = "edited after the fact"
    cast(dict[str, object], closure_previous["evidence_citations"])["7_revoked"] = [entry]
    cast(dict[str, object], closure_current["evidence_citations"])["7_revoked"] = [edited_entry]
    _expect("closure", closure_previous, closure_current, "7_revoked must stay byte-identical")


def test_43_bad_window_end_is_replayed_for_completion_and_activation_into_nine(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    anchor = _anchor(tmp_path)
    bad = _advance(anchor.state, "2026-10-10T21:00:00Z")
    bad["current_session"] = 8
    bad["session_status"] = "incomplete"
    bad["head_sha"] = NEW_COMMIT
    bad["required_completion_evidence"] = dict.fromkeys(SESSION_08_EVIDENCE_KEYS, False)
    write_state(anchor.repo / "docs/control/IMPLEMENTATION_STATE.json", bad)
    _commit(anchor.repo, "test: hand-made activation")
    previous = _session_eight_previous(anchor.repo)
    current = _session_eight_completion(previous)
    validate_completion_transition(previous, current)
    state_path = anchor.repo / "docs/control/IMPLEMENTATION_STATE.json"
    write_state(state_path, previous)
    candidate = anchor.tmp_path / "complete.json"
    write_state(candidate, current)
    with pytest.raises(ControlStateError, match="replay refused"):
        _apply_completion_transition(state_path, candidate, replay_anchor=anchor.sha)
    keys = dict(SESSION_EVIDENCE_KEYS)
    keys[9] = frozenset({"session_nine_marker", "evidence_closure_commit_recorded"})
    monkeypatch.setattr(control_state, "SESSION_EVIDENCE_KEYS", MappingProxyType(keys))
    into_nine_previous = _session_eight_complete(anchor.repo)
    into_nine = _activate_nine(into_nine_previous)
    validate_activation_transition(into_nine_previous, into_nine)
    write_state(state_path, into_nine_previous)
    nine_path = anchor.tmp_path / "into-nine.json"
    write_state(nine_path, into_nine)
    with pytest.raises(ControlStateError, match="replay refused"):
        _apply_activation_transition(state_path, nine_path, replay_anchor=anchor.sha)

    good = _anchor(tmp_path / "good")
    good.tmp_path = tmp_path / "good"
    state, commit_c, g7_digest = _record_through_eleven(good)
    closed = _close(good, state, commit_c, g7_digest)
    _commit(good.repo, "test: closure")
    activated = _advance(closed, "2026-10-10T18:30:00Z")
    activated["session_status"] = "incomplete"
    activated["current_session"] = 8
    activated["required_completion_evidence"] = dict.fromkeys(SESSION_08_EVIDENCE_KEYS, False)
    write_state(good.repo / "docs/control/IMPLEMENTATION_STATE.json", activated)
    _commit(good.repo, "test: valid activation")
    good_previous = _session_eight_previous(good.repo)
    good_current = _session_eight_completion(good_previous)
    validate_completion_transition(good_previous, good_current)
    good_state = good.repo / "docs/control/IMPLEMENTATION_STATE.json"
    write_state(good_state, good_previous)
    good_candidate = good.tmp_path / "complete.json"
    write_state(good_candidate, good_current)
    try:
        _apply_completion_transition(good_state, good_candidate, replay_anchor=good.sha)
    except ControlStateError as error:
        assert "replay refused" not in str(error)
    nine_previous = _session_eight_complete(good.repo)
    nine_current = _activate_nine(nine_previous)
    validate_activation_transition(nine_previous, nine_current)
    write_state(good_state, nine_previous)
    write_state(good.tmp_path / "nine.json", nine_current)
    try:
        _apply_activation_transition(
            good_state,
            good.tmp_path / "nine.json",
            replay_anchor=good.sha,
        )
    except ControlStateError as error:
        assert "replay refused" not in str(error)


def test_44_window_runs_to_head_until_a_valid_activation(tmp_path: Path) -> None:
    anchor = _anchor(tmp_path)
    citations = _plant(anchor.repo, (KEY_ONE,))
    merge = _commit(anchor.repo, "test: evidence")
    recorded = _apply_record(
        anchor, anchor.state, (KEY_ONE,), citations, merge, "2026-10-10T13:00:00Z"
    )
    _commit(anchor.repo, "test: record")
    tip = replay_state_history(anchor.repo, anchor.sha)
    assert tip["state_revision"] == recorded["state_revision"]
    assert tip["current_session"] == 7

    closed_anchor = _anchor(tmp_path / "closed")
    closed_anchor.tmp_path = tmp_path / "closed"
    state, commit_c, g7_digest = _record_through_eleven(closed_anchor)
    closed = _close(closed_anchor, state, commit_c, g7_digest)
    _commit(closed_anchor.repo, "test: closure")
    activated = _advance(closed, "2026-10-10T18:30:00Z")
    activated["session_status"] = "incomplete"
    activated["current_session"] = 8
    activated["required_completion_evidence"] = dict.fromkeys(SESSION_08_EVIDENCE_KEYS, False)
    write_state(closed_anchor.repo / "docs/control/IMPLEMENTATION_STATE.json", activated)
    _commit(closed_anchor.repo, "test: activation")
    later = _advance(activated, "2026-10-10T19:30:00Z")
    later["notes"] = {"changed": True}
    write_state(closed_anchor.repo / "docs/control/IMPLEMENTATION_STATE.json", later)
    _commit(closed_anchor.repo, "test: later session 08 edit")
    window_tip = replay_state_history(closed_anchor.repo, closed_anchor.sha)
    assert window_tip["current_session"] == 7
    assert window_tip["head_sha"] == commit_c

    invalid = _anchor(tmp_path / "invalid")
    citations = _plant(invalid.repo, (KEY_ONE,))
    merge = _commit(invalid.repo, "test: evidence")
    recorded = _apply_record(
        invalid, invalid.state, (KEY_ONE,), citations, merge, "2026-10-10T21:00:00Z"
    )
    _commit(invalid.repo, "test: still session 7")
    assert recorded["current_session"] == 7
    with pytest.raises(ControlStateError, match="bad window-end") as caught:
        replay_state_history(invalid.repo, invalid.sha, require_closed_window=True)
    assert str(caught.value) == "replay refused: bad window-end"


def test_state_py_frozen_ranges_stay_byte_identical() -> None:
    lines = (ROOT / "src/money_machine/control/state.py").read_text().splitlines(keepends=True)
    ranges = {
        (1, 598): "90dc28341d809341f3d2a3e76150672d3977f83111cc2288ec17cf5da116f55d",
        (399, 468): "ab1b02c8111645fec950bd53888a8df4cd7384e766e3eb3f974c94a2ca367dbd",
        (471, 598): "2573e42495732917d3ed70a76c79cc0a82992d8e94078adc663dcd9e5982d225",
    }
    for (start, end), digest in ranges.items():
        payload = "".join(lines[start - 1 : end]).encode()
        assert hashlib.sha256(payload).hexdigest() == digest


def _run_cli(
    state_path: Path,
    candidate: Path,
    command: str,
    *,
    env: dict[str, str] | None = None,
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
            str(candidate),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def _session_eight_previous(repo: Path) -> ControlState:
    previous = _fresh()
    previous["repo_root"] = str(repo)
    previous["branch"] = BRANCH
    previous["current_session"] = 8
    previous["session_status"] = "incomplete"
    previous["completed_sessions"] = list(range(8))
    previous["next_session"] = 8
    previous["next_prompt"] = SESSION_PROMPTS[8]
    previous["head_sha"] = NEW_COMMIT
    previous["evidence_closure_commit_sha"] = NEW_COMMIT
    previous["required_completion_evidence"] = {
        key: key != "evidence_closure_commit_recorded" for key in SESSION_08_EVIDENCE_KEYS
    }
    return previous


def _session_eight_completion(previous: ControlState) -> ControlState:
    current = _advance(previous, "2026-10-10T22:00:00Z")
    current["session_status"] = "complete"
    current["completed_sessions"] = list(range(9))
    current["next_session"] = 9
    current["next_prompt"] = SESSION_PROMPTS[9]
    evidence = cast(dict[str, bool], current["required_completion_evidence"])
    evidence["evidence_closure_commit_recorded"] = True
    current["head_sha"] = OTHER_COMMIT
    current["evidence_closure_commit_sha"] = OTHER_COMMIT
    contract = dict(current["transition_contract"])
    contract["completion_requires_next_session"] = 9
    current["transition_contract"] = contract
    return current


def _session_eight_complete(repo: Path) -> ControlState:
    previous = _session_eight_previous(repo)
    previous["session_status"] = "complete"
    previous["completed_sessions"] = list(range(9))
    previous["next_session"] = 9
    previous["next_prompt"] = SESSION_PROMPTS[9]
    previous["required_completion_evidence"] = dict.fromkeys(SESSION_08_EVIDENCE_KEYS, True)
    contract = dict(previous["transition_contract"])
    contract["completion_requires_next_session"] = 9
    previous["transition_contract"] = contract
    return previous


def _activate_nine(previous: ControlState) -> ControlState:
    current = _advance(previous, "2026-10-10T22:30:00Z")
    current["current_session"] = 9
    current["session_status"] = "incomplete"
    current["required_completion_evidence"] = {
        "session_nine_marker": False,
        "evidence_closure_commit_recorded": False,
    }
    return current
