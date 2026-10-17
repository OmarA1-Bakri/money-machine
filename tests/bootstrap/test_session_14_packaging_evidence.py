"""The Session 14 packaging key flips only through the proof-gated transition."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import cast

import pytest
import yaml

from money_machine.control.session_14_proof import EARNED_EVIDENCE_KEYS, prove_session_14
from money_machine.control.state import (
    SESSION_EVIDENCE_KEYS,
    ControlState,
    ControlStateError,
    validate_session_14_evidence_record,
)
from money_machine.deploy.packaging import (
    RUNBOOKS,
    PackagingRefusal,
    define_production_package,
    inspect_production_package,
)

ROOT = Path(__file__).parents[2]
STATE_PATH = ROOT / "docs/control/IMPLEMENTATION_STATE.json"
EARNED_AT = "2026-10-17T15:10:00Z"


def _live() -> ControlState:
    loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("state file must be an object")
    return cast(ControlState, copy.deepcopy(loaded))


def _previous() -> ControlState:
    """Revision 106, rebuilt after the packaging record replaces the live file."""
    state = _live()
    state["state_revision"] = 106
    state["current_session"] = 14
    state["session_status"] = "incomplete"
    state["updated_at"] = "2026-10-17T15:00:00Z"
    evidence = dict.fromkeys(sorted(SESSION_EVIDENCE_KEYS[14]), False)
    evidence["deployment_target_recorded"] = True
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


def _document() -> dict[str, object]:
    loaded = yaml.safe_load((ROOT / "compose.prod.yaml").read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError("compose file must be a mapping")
    return cast(dict[str, object], loaded)


def _runbooks() -> dict[str, str]:
    return {relative: (ROOT / relative).read_text(encoding="utf-8") for relative in RUNBOOKS}


def test_package_names_the_fail_closed_services() -> None:
    package = define_production_package(ROOT)
    assert package.services == ("postgres", "api", "web", "worker", "scheduler")
    assert package.postgres_volume == "postgres-data"
    assert package.healthchecks == ("postgres", "api")
    assert package.worker_restart == "no"
    assert package.scheduler_restart == "no"
    assert package.runbooks == RUNBOOKS
    assert package.docker_compose_config_ran is False


def test_package_refuses_a_compose_config_shortcut() -> None:
    with pytest.raises(PackagingRefusal, match="compose_config"):
        define_production_package(ROOT, accept_compose_config=True)


def test_package_refuses_a_restart_that_would_commission_the_worker() -> None:
    document = _document()
    services = document["services"]
    assert isinstance(services, dict)
    worker = services["worker"]
    assert isinstance(worker, dict)
    worker["restart"] = "unless-stopped"
    with pytest.raises(PackagingRefusal, match="restart"):
        inspect_production_package(document, _runbooks())


def test_package_refuses_a_runbook_secret_and_a_missing_exit_78() -> None:
    runbooks = _runbooks()
    secret = dict(runbooks)
    secret["docs/runbooks/INCIDENTS.md"] = "api_key: sk-live-secretvalue\n"
    with pytest.raises(PackagingRefusal, match="secret"):
        inspect_production_package(_document(), secret)
    missing = dict(runbooks)
    missing["docs/runbooks/INCIDENTS.md"] = "The worker is not commissioned.\n"
    with pytest.raises(PackagingRefusal, match="exit_78"):
        inspect_production_package(_document(), missing)


def test_package_refuses_a_literal_database_password() -> None:
    document = _document()
    services = document["services"]
    assert isinstance(services, dict)
    postgres = services["postgres"]
    assert isinstance(postgres, dict)
    environment = postgres["environment"]
    assert isinstance(environment, dict)
    environment["POSTGRES_PASSWORD"] = "committed-value"
    with pytest.raises(PackagingRefusal, match="secret"):
        inspect_production_package(document, _runbooks())


def test_proof_earns_the_target_and_the_package() -> None:
    assert prove_session_14() == EARNED_EVIDENCE_KEYS


def test_record_accepts_the_package_and_refuses_the_closure_key() -> None:
    previous = _previous()
    validate_session_14_evidence_record(previous, _earned(previous))
    closure = _earned(previous)
    evidence = dict(closure["required_completion_evidence"])
    evidence["evidence_closure_commit_recorded"] = True
    closure["required_completion_evidence"] = evidence
    with pytest.raises(ControlStateError, match="closure key stays false"):
        validate_session_14_evidence_record(previous, closure)
