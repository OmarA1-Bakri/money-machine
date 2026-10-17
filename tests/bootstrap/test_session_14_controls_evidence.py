"""The Session 14 service-control key flips only through the proof-gated transition."""

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
from money_machine.deploy.controls import (
    SERVICE_CONTROLS,
    ServiceControlRefusal,
    confirm_exit_78_held,
    control_service,
)

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
EARNED_AT = "2026-10-17T15:25:00Z"


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _previous() -> ControlState:
    """Revision 108, the pointer before the service-control record."""
    state = _live()
    state["state_revision"] = 108
    state["current_session"] = 14
    state["session_status"] = "incomplete"
    state["updated_at"] = "2026-10-17T15:15:00Z"
    evidence = dict.fromkeys(sorted(SESSION_EVIDENCE_KEYS[14]), False)
    evidence["deployment_target_recorded"] = True
    evidence["production_packaging_defined"] = True
    evidence["release_rollback_implemented"] = True
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


def test_every_named_control_is_refused() -> None:
    held = confirm_exit_78_held(ROOT)
    assert held.worker_held is True
    assert held.scheduler_held is True
    assert held.running is False
    for action in SERVICE_CONTROLS:
        expected = "scheduler_singleton" if action == "scheduler_singleton" else "closed"
        with pytest.raises(ServiceControlRefusal, match=expected) as caught:
            control_service(action)
        assert caught.value.running is False


def test_a_status_word_is_not_a_running_service() -> None:
    with pytest.raises(ServiceControlRefusal, match="status_word") as caught:
        control_service("status", status_word="running")
    assert caught.value.running is False
    with pytest.raises(ServiceControlRefusal, match="docker_socket"):
        control_service("start", docker_socket=True)


def test_a_second_scheduler_is_refused() -> None:
    with pytest.raises(ServiceControlRefusal, match="scheduler_singleton"):
        control_service("start", service="scheduler", scheduler_count=1)
    with pytest.raises(ServiceControlRefusal, match="scheduler_singleton"):
        control_service("scale", service="scheduler", replicas=2)
    with pytest.raises(ServiceControlRefusal, match="closed"):
        control_service("start", service="scheduler", scheduler_count=0)
    with pytest.raises(ServiceControlRefusal, match="unknown"):
        control_service("commission")


def test_proof_earns_the_control_key() -> None:
    assert prove_session_14() == EARNED_EVIDENCE_KEYS
    assert "service_controls_fail_closed" in EARNED_EVIDENCE_KEYS


def test_record_accepts_the_controls_and_refuses_the_closure_key() -> None:
    previous = _previous()
    validate_session_14_evidence_record(previous, _earned(previous))
    closure = _earned(previous)
    evidence = dict(closure["required_completion_evidence"])
    evidence["evidence_closure_commit_recorded"] = True
    closure["required_completion_evidence"] = evidence
    with pytest.raises(ControlStateError, match="closure key stays false"):
        validate_session_14_evidence_record(previous, closure)


def test_record_refuses_the_control_file_key() -> None:
    previous = _previous()
    current = _earned(previous)
    evidence = dict(current["required_completion_evidence"])
    evidence["control_files_and_checkpoint_current"] = True
    current["required_completion_evidence"] = evidence
    with pytest.raises(ControlStateError, match="exactly the keys"):
        validate_session_14_evidence_record(previous, current)
