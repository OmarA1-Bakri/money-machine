"""The session evidence index matches the completion commits and the live pointer."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from money_machine.control.session_evidence import (
    CLOSED_SESSION_EVIDENCE,
    OPEN_SESSION_EVIDENCE,
    render_session_evidence,
)
from money_machine.control.state import SESSION_EVIDENCE_KEYS, SESSION_PROMPTS

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
INDEX_PATH = ROOT / "docs/SESSION_EVIDENCE.md"


def _state_at(commit: str) -> dict[str, object]:
    raw = subprocess.check_output(
        ["git", "show", f"{commit}:docs/control/IMPLEMENTATION_STATE.json"],
        cwd=ROOT,
        text=True,
    )
    loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return loaded


def test_every_session_from_00_through_15_is_listed_once() -> None:
    closed = [record.session for record in CLOSED_SESSION_EVIDENCE]
    opened = [record.session for record in OPEN_SESSION_EVIDENCE]
    assert closed == list(range(8))
    assert opened == list(range(8, 16))
    assert set(closed).isdisjoint(opened)


def test_closed_snapshots_match_the_commits_that_hold_them() -> None:
    for record in CLOSED_SESSION_EVIDENCE:
        state = _state_at(record.state_commit)
        assert state["current_session"] == record.session
        assert state["session_status"] == "complete"
        assert state["state_revision"] == record.state_revision
        assert state["next_session"] == record.next_session
        assert state["completed_sessions"] == list(record.completed_sessions)
        assert state["next_prompt"] == SESSION_PROMPTS[record.next_session]
        assert state["evidence_closure_commit_sha"] == record.evidence_closure_commit_sha
        assert state["head_sha"] == record.head_sha
        evidence = state["required_completion_evidence"]
        assert isinstance(evidence, dict)
        assert set(evidence) == set(SESSION_EVIDENCE_KEYS[record.session])
        values = list(evidence.values())
        assert all(isinstance(item, bool) for item in values)
        assert all(item is record.all_keys_true for item in values)


def test_live_pointer_still_matches_the_session_07_close() -> None:
    live = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    record = CLOSED_SESSION_EVIDENCE[7]
    assert live["current_session"] == 7
    assert live["session_status"] == "complete"
    assert live["state_revision"] == record.state_revision
    assert live["head_sha"] == record.head_sha
    assert live["evidence_closure_commit_sha"] == record.evidence_closure_commit_sha
    assert live["required_completion_evidence"] == {
        key: False for key in sorted(SESSION_EVIDENCE_KEYS[7])
    }


def test_open_sessions_have_no_recorded_true_key() -> None:
    for record in OPEN_SESSION_EVIDENCE:
        assert record.session not in {item.session for item in CLOSED_SESSION_EVIDENCE}
        defined = record.session in SESSION_EVIDENCE_KEYS
        assert defined is (record.session == 8)
        for path in record.fixture_paths:
            assert (ROOT / path).is_file(), path
        assert "not" in record.gap.casefold() or "no evidence" in record.gap.casefold()


def test_index_is_the_rendered_catalogue() -> None:
    assert INDEX_PATH.read_text(encoding="utf-8") == render_session_evidence()
