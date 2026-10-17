"""The acceptance-matrix key flips only through the proof-gated transition."""

from __future__ import annotations

import pytest

from money_machine.assets.acceptance_matrix import (
    AcceptanceItem,
    AcceptanceMatrixRefusal,
    Verdict,
    accept_page,
    counts_as_pass,
    record_acceptance_matrix,
    refuse_exit_string,
    validate_acceptance,
)
from money_machine.control.session_15_proof import EARNED_EVIDENCE_KEYS, prove_session_15

_LIVE = frozenset(
    {
        "private_repository",
        "postgresql_source_of_truth",
        "notion_product",
        "live_publication",
        "automatic_cull",
        "posthog",
        "production_deploy_and_backup",
        "live_credentials",
        "real_workflow",
    }
)


def test_every_definition_item_is_marked() -> None:
    recorded = record_acceptance_matrix()
    assert len(recorded.items) == 25
    assert recorded.live_call is False
    assert {item.verdict for item in recorded.items} <= {
        Verdict.PASS,
        Verdict.FAIL,
        Verdict.BLOCKED_EXTERNAL,
    }
    assert {item.name for item in recorded.items if item.name in _LIVE} == _LIVE
    assert all(
        item.verdict is Verdict.BLOCKED_EXTERNAL for item in recorded.items if item.name in _LIVE
    )
    assert any(item.verdict is Verdict.FAIL for item in recorded.items)
    assert "HANDS_OFF_MONEY_MACHINE_COMMISSIONED" not in recorded.handover
    assert "SESSION_14_PRODUCTION_DEPLOYMENT_COMPLETE" not in recorded.handover


def test_a_fail_is_not_a_pass() -> None:
    assert counts_as_pass(Verdict.PASS) is True
    assert counts_as_pass(Verdict.FAIL) is False
    assert counts_as_pass(Verdict.BLOCKED_EXTERNAL) is False


def test_a_live_item_cannot_be_marked_pass() -> None:
    recorded = record_acceptance_matrix()
    items = tuple(
        AcceptanceItem(item.number, item.name, Verdict.PASS, item.evidence)
        if item.name == "live_credentials"
        else item
        for item in recorded.items
    )
    with pytest.raises(AcceptanceMatrixRefusal, match="live_item"):
        validate_acceptance(items)


def test_a_page_does_not_earn_the_key() -> None:
    with pytest.raises(AcceptanceMatrixRefusal, match="page"):
        accept_page("the machine is ready")


def test_the_handover_refuses_the_exit_string() -> None:
    with pytest.raises(AcceptanceMatrixRefusal, match="exit_string"):
        refuse_exit_string("HANDS_OFF_MONEY_MACHINE_COMMISSIONED")


def test_proof_earns_the_acceptance_matrix_key() -> None:
    assert prove_session_15() == EARNED_EVIDENCE_KEYS
    assert "acceptance_matrix_recorded" in EARNED_EVIDENCE_KEYS
