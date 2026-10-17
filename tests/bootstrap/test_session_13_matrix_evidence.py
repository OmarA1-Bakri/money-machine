"""The Session 13 matrix key flips only through the proof-gated transition."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import cast

import pytest

from money_machine.assets.implementation_matrix import (
    MatrixRefusal,
    MatrixRow,
    MatrixStatus,
    build_matrix,
    validate_matrix,
)
from money_machine.control.session_13_proof import EARNED_EVIDENCE_KEYS, prove_session_13
from money_machine.control.state import (
    SESSION_EVIDENCE_KEYS,
    ControlState,
    ControlStateError,
    validate_session_13_evidence_record,
)

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
EARNED_AT = "2026-10-17T14:00:00Z"


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _previous() -> ControlState:
    """Revision 98, rebuilt after the matrix record replaces the live file."""
    state = _live()
    state["state_revision"] = 98
    state["current_session"] = 13
    state["session_status"] = "incomplete"
    state["updated_at"] = "2026-10-17T13:45:00Z"
    state["required_completion_evidence"] = dict.fromkeys(sorted(SESSION_EVIDENCE_KEYS[13]), False)
    return state


def _earned(previous: ControlState) -> ControlState:
    current = copy.deepcopy(previous)
    current["state_revision"] = previous["state_revision"] + 1
    current["updated_at"] = EARNED_AT
    evidence = dict(current["required_completion_evidence"])
    for key in EARNED_EVIDENCE_KEYS:
        evidence[key] = True
    current["required_completion_evidence"] = evidence
    return current


def test_matrix_blocks_live_provider_jobs_and_keeps_fail_closed_agents_missing() -> None:
    rows = build_matrix(ROOT)
    by_name = {(row.surface, row.name): row for row in rows}
    publish = by_name[("job_type", "PublishListingJob")]
    assert publish.status is MatrixStatus.BLOCKED_BY_EXTERNAL_CREDENTIAL
    assert by_name[("job_type", "CompetitorPurchaseJob")].status is (
        MatrixStatus.BLOCKED_BY_EXTERNAL_CREDENTIAL
    )
    assert by_name[("agent", "A01")].status is MatrixStatus.IMPLEMENTED_NOT_LIVE_TESTED
    assert by_name[("agent", "A03")].status is MatrixStatus.MISSING
    assert by_name[("runbook", "worker_crash")].status is MatrixStatus.MISSING
    weekly = by_name[("playbook_step", "weekly_metrics")]
    assert weekly.status is MatrixStatus.IMPLEMENTED_AND_TESTED


def test_matrix_refuses_a_live_job_marked_tested() -> None:
    rows = build_matrix(ROOT)
    relabeled = tuple(
        MatrixRow(
            surface=row.surface,
            name=row.name,
            status=MatrixStatus.IMPLEMENTED_AND_TESTED,
            evidence="src/money_machine/domain/events.py",
        )
        if row.name == "PublishListingJob"
        else row
        for row in rows
    )
    with pytest.raises(MatrixRefusal, match="blocked_job"):
        validate_matrix(relabeled, ROOT)


def test_proof_earns_only_the_matrix_key() -> None:
    assert prove_session_13() == EARNED_EVIDENCE_KEYS


def test_record_accepts_the_matrix_key_and_refuses_the_closure_key() -> None:
    previous = _previous()
    validate_session_13_evidence_record(previous, _earned(previous))
    closure = _earned(previous)
    evidence = dict(closure["required_completion_evidence"])
    evidence["evidence_closure_commit_recorded"] = True
    closure["required_completion_evidence"] = evidence
    with pytest.raises(ControlStateError, match="closure key stays false"):
        validate_session_13_evidence_record(previous, closure)


def test_record_refuses_a_second_unearned_key() -> None:
    previous = _previous()
    current = _earned(previous)
    evidence = dict(current["required_completion_evidence"])
    evidence["synthetic_paths_implemented"] = True
    current["required_completion_evidence"] = evidence
    with pytest.raises(ControlStateError, match="exactly the keys the fixture proof earned"):
        validate_session_13_evidence_record(previous, current)
