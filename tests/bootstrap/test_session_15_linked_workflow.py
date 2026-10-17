"""The linked-workflow key flips only through the proof-gated transition."""

from __future__ import annotations

import pytest

from money_machine.assets.linked_workflow import (
    LinkedWorkflowRefusal,
    advance_linked_workflow,
    run_linked_workflow,
)
from money_machine.control.session_15_proof import EARNED_EVIDENCE_KEYS, prove_session_15


def test_the_fixture_chain_stops_at_preflight() -> None:
    recorded = run_linked_workflow()
    assert recorded.stopped_at == "preflight"
    assert recorded.provider == "fixture"
    assert recorded.listing_count >= 1
    assert recorded.notion_connected is True
    assert recorded.preflight_passed is True
    assert recorded.published is False
    assert recorded.purchased is False
    assert recorded.checkout is False


@pytest.mark.parametrize("action", ["publish", "purchase", "checkout"])
@pytest.mark.parametrize("enabled", [True, False])
def test_a_true_flag_does_not_continue(action: str, enabled: bool) -> None:
    with pytest.raises(LinkedWorkflowRefusal, match=action):
        if action == "publish":
            advance_linked_workflow("publish", enabled=enabled)
        elif action == "purchase":
            advance_linked_workflow("purchase", enabled=enabled)
        else:
            advance_linked_workflow("checkout", enabled=enabled)


def test_proof_earns_the_linked_workflow_key() -> None:
    assert prove_session_15() == EARNED_EVIDENCE_KEYS
    assert "linked_workflow_fixture" in EARNED_EVIDENCE_KEYS
