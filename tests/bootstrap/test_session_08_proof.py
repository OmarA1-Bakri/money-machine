"""The Session 08 fixture proof earns the behavioral keys and no closure key."""

from __future__ import annotations

from money_machine.control.session_08_proof import (
    BEHAVIORAL_EVIDENCE_KEYS,
    CLOSURE_EVIDENCE_KEY,
    CONTROL_EVIDENCE_KEY,
    prove_session_08,
)


def test_fixture_proof_earns_the_behavioral_keys() -> None:
    earned = prove_session_08()

    assert earned == BEHAVIORAL_EVIDENCE_KEYS
    assert CONTROL_EVIDENCE_KEY not in earned
    assert CLOSURE_EVIDENCE_KEY not in earned
