"""The Session 14 release key flips only through the proof-gated transition."""

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
from money_machine.deploy.release import (
    ReleaseRefusal,
    bound_image_tag,
    plan_release,
    rollback_image,
)

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
COMMIT = "fbaf8e8bdd73b1e3b6fa4f87158574057b72d18a"
EARNED_AT = "2026-10-17T15:15:00Z"


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _previous() -> ControlState:
    """Revision 107, the pointer before the release record."""
    state = _live()
    state["state_revision"] = 107
    state["current_session"] = 14
    state["session_status"] = "incomplete"
    state["updated_at"] = "2026-10-17T15:10:00Z"
    evidence = dict.fromkeys(sorted(SESSION_EVIDENCE_KEYS[14]), False)
    evidence["deployment_target_recorded"] = True
    evidence["production_packaging_defined"] = True
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


def test_release_binds_the_tag_and_plans_a_fixture_backup() -> None:
    plan = plan_release(
        commit_sha=COMMIT,
        image_tag=bound_image_tag(COMMIT),
        mode="fixture",
        deployed_revision="base",
        candidate_revision="forward",
    )
    assert plan.image_tag == f"money-machine:{COMMIT}"
    assert plan.commit_sha == COMMIT
    assert plan.backup_planned is True
    assert plan.schema_compatible is True
    assert plan.rollback_safe is True
    assert plan.image_pushed is False
    rolled = rollback_image(plan)
    assert rolled.image_pushed is False


def test_release_refuses_live_postgres_and_an_image_push() -> None:
    with pytest.raises(ReleaseRefusal, match="live_postgres"):
        plan_release(
            commit_sha=COMMIT,
            image_tag=bound_image_tag(COMMIT),
            mode="postgres",
            deployed_revision="base",
            candidate_revision="forward",
        )
    with pytest.raises(ReleaseRefusal, match="image_push"):
        plan_release(
            commit_sha=COMMIT,
            image_tag=bound_image_tag(COMMIT),
            mode="fixture",
            deployed_revision="base",
            candidate_revision="forward",
            push=True,
        )


def test_release_refuses_an_unbound_tag_and_an_incompatible_schema() -> None:
    with pytest.raises(ReleaseRefusal, match="unbound_tag"):
        plan_release(
            commit_sha="abc",
            image_tag="money-machine:abc",
            mode="fixture",
            deployed_revision="base",
            candidate_revision="forward",
        )
    with pytest.raises(ReleaseRefusal, match="unbound_tag"):
        plan_release(
            commit_sha=COMMIT,
            image_tag="money-machine:latest",
            mode="fixture",
            deployed_revision="base",
            candidate_revision="forward",
        )
    with pytest.raises(ReleaseRefusal, match="incompatible_schema"):
        plan_release(
            commit_sha=COMMIT,
            image_tag=bound_image_tag(COMMIT),
            mode="fixture",
            deployed_revision="base",
            candidate_revision="other",
        )


def test_release_refuses_backup_skip_before_a_live_database() -> None:
    with pytest.raises(ReleaseRefusal, match="backup_required"):
        plan_release(
            commit_sha=COMMIT,
            image_tag=bound_image_tag(COMMIT),
            mode="postgres",
            deployed_revision="base",
            candidate_revision="forward",
            backup_before_migrate=False,
        )


def test_destructive_schema_is_not_an_image_rollback() -> None:
    plan = plan_release(
        commit_sha=COMMIT,
        image_tag=bound_image_tag(COMMIT),
        mode="fixture",
        deployed_revision="base",
        candidate_revision="cleanup",
    )
    assert plan.backup_planned is True
    assert plan.schema_compatible is True
    assert plan.rollback_safe is False
    assert plan.image_pushed is False
    with pytest.raises(ReleaseRefusal, match="rollback_refused"):
        rollback_image(plan)


def test_proof_earns_the_release_key() -> None:
    assert prove_session_14() == EARNED_EVIDENCE_KEYS
    assert "release_rollback_implemented" in EARNED_EVIDENCE_KEYS


def test_record_accepts_the_release_and_refuses_the_closure_key() -> None:
    previous = _previous()
    validate_session_14_evidence_record(previous, _earned(previous))
    closure = _earned(previous)
    evidence = dict(closure["required_completion_evidence"])
    evidence["evidence_closure_commit_recorded"] = True
    closure["required_completion_evidence"] = evidence
    with pytest.raises(ControlStateError, match="closure key stays false"):
        validate_session_14_evidence_record(previous, closure)


def test_record_refuses_a_service_control_key() -> None:
    previous = _previous()
    current = _earned(previous)
    evidence = dict(current["required_completion_evidence"])
    evidence["control_files_and_checkpoint_current"] = True
    current["required_completion_evidence"] = evidence
    with pytest.raises(ControlStateError, match="exactly the keys"):
        validate_session_14_evidence_record(previous, current)
