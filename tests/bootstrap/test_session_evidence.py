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
INDEX_PATH = ROOT / "docs/control/SESSION_EVIDENCE.md"


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
    assert closed == list(range(11))
    assert opened == list(range(11, 16))
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


def test_live_pointer_is_incomplete_session_14() -> None:
    live = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    assert live["current_session"] == 15
    assert live["session_status"] == "incomplete"
    assert live["state_revision"] == 117
    assert live["completed_sessions"] == list(range(15))
    assert live["next_session"] == 15
    assert live["next_prompt"] == SESSION_PROMPTS[15]
    assert live["head_sha"] == "02c26f39ac8800db03ae7f5d1d346487a5ce123e"
    assert live["evidence_closure_commit_sha"] == live["head_sha"]
    evidence = live["required_completion_evidence"]
    assert isinstance(evidence, dict)
    expected = {key: False for key in sorted(SESSION_EVIDENCE_KEYS[15])}
    expected["deployed_state_checked"] = True
    expected["provider_connections_fail_closed"] = True
    expected["standing_authority_recorded"] = True
    expected["linked_workflow_fixture"] = True
    expected["acceptance_matrix_recorded"] = True
    assert evidence == expected


def test_open_sessions_have_no_recorded_true_key() -> None:
    for record in OPEN_SESSION_EVIDENCE:
        assert record.session not in {item.session for item in CLOSED_SESSION_EVIDENCE}
        if record.session == 11:
            assert record.session in SESSION_EVIDENCE_KEYS
            assert record.activated is True
            assert record.true_keys == frozenset(SESSION_EVIDENCE_KEYS[11])
        elif record.session == 12:
            assert record.session in SESSION_EVIDENCE_KEYS
            assert record.activated is True
            assert record.true_keys == frozenset(SESSION_EVIDENCE_KEYS[12])
        elif record.session == 13:
            assert record.session in SESSION_EVIDENCE_KEYS
            assert record.activated is True
            assert record.true_keys == frozenset(SESSION_EVIDENCE_KEYS[13])
        elif record.session == 14:
            assert record.session in SESSION_EVIDENCE_KEYS
            assert record.activated is True
            assert record.true_keys == frozenset(
                {
                    "deployment_target_recorded",
                    "production_packaging_defined",
                    "release_rollback_implemented",
                    "service_controls_fail_closed",
                    "control_files_and_checkpoint_current",
                    "evidence_closure_commit_recorded",
                }
            )
        elif record.session == 15:
            assert record.session in SESSION_EVIDENCE_KEYS
            assert record.activated is True
            assert record.true_keys == frozenset(
                {
                    "acceptance_matrix_recorded",
                    "deployed_state_checked",
                    "linked_workflow_fixture",
                    "provider_connections_fail_closed",
                    "standing_authority_recorded",
                }
            )
        else:
            assert record.session not in SESSION_EVIDENCE_KEYS
            assert record.true_keys == frozenset()
        for path in record.fixture_paths:
            assert (ROOT / path).is_file(), path
        assert "not" in record.gap.casefold() or "no evidence" in record.gap.casefold()


def test_index_is_the_rendered_catalogue() -> None:
    assert INDEX_PATH.read_text(encoding="utf-8") == render_session_evidence()
