"""The Session 14 checkpoint key flips only through the proof-gated transition."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import cast

import pytest

from money_machine.control.session_14_proof import EARNED_EVIDENCE_KEYS, prove_session_14
from money_machine.control.state import (
    SESSION_EVIDENCE_KEYS,
    ControlState,
    ControlStateError,
    validate_session_14_evidence_record,
)
from money_machine.deploy.checkpoint import (
    CONTROL_FILES,
    DEPLOY_MODULES,
    CheckpointRefusal,
    inspect_deployment_checkpoint,
)

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
EARNED_AT = "2026-10-17T15:30:00Z"
CLOSURE_HEAD = "02c26f39ac8800db03ae7f5d1d346487a5ce123e"
PREVIOUS_REVISION = 109
PREVIOUS_AT = "2026-10-17T15:25:00Z"
PREVIOUS_KEYS = frozenset(
    {
        "deployment_target_recorded",
        "production_packaging_defined",
        "release_rollback_implemented",
        "service_controls_fail_closed",
    }
)
LIVE_REVISION = 117
LIVE_AT = "2026-10-17T16:35:00Z"
LIVE_KEYS: frozenset[str] = frozenset(
    {
        "acceptance_matrix_recorded",
        "deployed_state_checked",
        "linked_workflow_fixture",
        "provider_connections_fail_closed",
        "standing_authority_recorded",
    }
)


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _previous() -> ControlState:
    """Revision 109, the pointer before the checkpoint record."""
    state = _live()
    state["state_revision"] = PREVIOUS_REVISION
    state["current_session"] = 14
    state["session_status"] = "incomplete"
    state["updated_at"] = PREVIOUS_AT
    evidence = dict.fromkeys(sorted(SESSION_EVIDENCE_KEYS[14]), False)
    for key in PREVIOUS_KEYS:
        evidence[key] = True
    state["required_completion_evidence"] = evidence
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


def test_checkpoint_matches_the_continuity_files() -> None:
    checkpoint = inspect_deployment_checkpoint(
        ROOT,
        expected_revision=LIVE_REVISION,
        expected_updated_at=LIVE_AT,
        expected_true_keys=LIVE_KEYS,
        closure_head=CLOSURE_HEAD,
    )
    assert checkpoint.revision == LIVE_REVISION
    assert checkpoint.updated_at == LIVE_AT
    assert checkpoint.head_sha == CLOSURE_HEAD
    assert checkpoint.true_keys == tuple(sorted(LIVE_KEYS))
    assert checkpoint.catalogue_matches is True
    assert checkpoint.closure_recorded is False
    assert checkpoint.exit_string_present is False


def test_a_partial_closure_claim_is_refused() -> None:
    claimed = PREVIOUS_KEYS | {"evidence_closure_commit_recorded"}
    with pytest.raises(CheckpointRefusal, match="keys"):
        inspect_deployment_checkpoint(
            ROOT,
            expected_revision=PREVIOUS_REVISION,
            expected_updated_at=PREVIOUS_AT,
            expected_true_keys=claimed,
            closure_head=CLOSURE_HEAD,
        )


def test_a_short_key_set_is_refused() -> None:
    with pytest.raises(CheckpointRefusal, match="keys"):
        inspect_deployment_checkpoint(
            ROOT,
            expected_revision=LIVE_REVISION,
            expected_updated_at=LIVE_AT,
            expected_true_keys=frozenset({"deployment_target_recorded"}),
            closure_head=CLOSURE_HEAD,
        )


def _scratch(tmp_path: Path, *, state: str, decisions: str) -> None:
    for relative in CONTROL_FILES + DEPLOY_MODULES:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.name == "IMPLEMENTATION_STATE.json":
            path.write_text(state, encoding="utf-8")
        elif path.name == "DECISIONS.md":
            path.write_text(decisions, encoding="utf-8")
        elif not path.exists():
            path.write_text("present\n", encoding="utf-8")


def test_the_exit_string_in_the_state_file_is_refused(tmp_path: Path) -> None:
    _scratch(
        tmp_path,
        state='{"claim": "SESSION_14_PRODUCTION_DEPLOYMENT_COMPLETE"}\n',
        decisions="D-0085\n",
    )
    with pytest.raises(CheckpointRefusal, match="exit_string"):
        inspect_deployment_checkpoint(
            tmp_path,
            expected_revision=LIVE_REVISION,
            expected_updated_at=LIVE_AT,
            expected_true_keys=LIVE_KEYS,
            closure_head=CLOSURE_HEAD,
        )


def test_a_bare_exit_string_in_the_decisions_is_refused(tmp_path: Path) -> None:
    _scratch(
        tmp_path,
        state="{}\n",
        decisions="SESSION_14_PRODUCTION_DEPLOYMENT_COMPLETE\n",
    )
    with pytest.raises(CheckpointRefusal, match="exit_string"):
        inspect_deployment_checkpoint(
            tmp_path,
            expected_revision=LIVE_REVISION,
            expected_updated_at=LIVE_AT,
            expected_true_keys=LIVE_KEYS,
            closure_head=CLOSURE_HEAD,
        )


def test_a_missing_continuity_file_is_refused(tmp_path: Path) -> None:
    with pytest.raises(CheckpointRefusal, match="control_files"):
        inspect_deployment_checkpoint(
            tmp_path,
            expected_revision=LIVE_REVISION,
            expected_updated_at=LIVE_AT,
            expected_true_keys=LIVE_KEYS,
            closure_head=CLOSURE_HEAD,
        )


def test_proof_earns_the_checkpoint_key() -> None:
    assert prove_session_14() == EARNED_EVIDENCE_KEYS
    assert "control_files_and_checkpoint_current" in EARNED_EVIDENCE_KEYS


def test_record_accepts_the_checkpoint_and_refuses_the_closure_key() -> None:
    previous = _previous()
    validate_session_14_evidence_record(previous, _earned(previous))
    closure = _earned(previous)
    evidence = dict(closure["required_completion_evidence"])
    evidence["evidence_closure_commit_recorded"] = True
    closure["required_completion_evidence"] = evidence
    with pytest.raises(ControlStateError, match="closure key stays false"):
        validate_session_14_evidence_record(previous, closure)


def test_record_refuses_a_partial_checkpoint() -> None:
    previous = _previous()
    current = _earned(previous)
    evidence = dict(current["required_completion_evidence"])
    evidence["control_files_and_checkpoint_current"] = False
    current["required_completion_evidence"] = evidence
    with pytest.raises(ControlStateError, match="at least one key"):
        validate_session_14_evidence_record(previous, current)
