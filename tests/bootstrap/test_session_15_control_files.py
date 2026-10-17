"""The continuity key flips only through the proof-gated transition."""

from __future__ import annotations

from pathlib import Path

import pytest

from money_machine.control.session_15_proof import EARNED_EVIDENCE_KEYS, prove_session_15
from money_machine.deploy.continuity import (
    ContinuityRefusal,
    narratives_cite,
    record_control_checkpoint,
    refuse_commissioning_page,
)

ROOT = Path(__file__).parents[2]
CLOSURE_HEAD = "02c26f39ac8800db03ae7f5d1d346487a5ce123e"
POINTER_REVISION = 118
UPDATED_AT = "2026-10-17T16:45:00Z"
TRUE_KEYS = frozenset(
    {
        "acceptance_matrix_recorded",
        "control_files_and_checkpoint_current",
        "deployed_state_checked",
        "linked_workflow_fixture",
        "provider_connections_fail_closed",
        "standing_authority_recorded",
    }
)


def test_the_continuity_files_match_the_pointer() -> None:
    recorded = record_control_checkpoint(
        expected_revision=POINTER_REVISION,
        expected_updated_at=UPDATED_AT,
        expected_true_keys=TRUE_KEYS,
        closure_head=CLOSURE_HEAD,
    )
    assert recorded.revision == POINTER_REVISION
    assert recorded.updated_at == UPDATED_AT
    assert recorded.closure_recorded is False
    assert recorded.exit_string_present is False
    assert recorded.true_keys == tuple(sorted(TRUE_KEYS))
    assert "evidence_closure_commit_recorded" not in recorded.true_keys
    assert len(recorded.files_read) == 6


def test_the_closure_key_is_refused() -> None:
    with pytest.raises(ContinuityRefusal, match="closure"):
        record_control_checkpoint(
            expected_revision=POINTER_REVISION,
            expected_updated_at=UPDATED_AT,
            expected_true_keys=TRUE_KEYS | {"evidence_closure_commit_recorded"},
            closure_head=CLOSURE_HEAD,
        )


def test_a_stale_narrative_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "docs" / "control"
    folder.mkdir(parents=True)
    for name in (
        "IMPLEMENTATION_LOG.md",
        "DECISIONS.md",
        "TEST_EVIDENCE.md",
        "NEXT_SESSION.md",
    ):
        (folder / name).write_text("revision 1\n", encoding="utf-8")
    with pytest.raises(ContinuityRefusal, match="stale"):
        narratives_cite(tmp_path, 117, UPDATED_AT)


def test_a_page_does_not_earn_the_key() -> None:
    with pytest.raises(ContinuityRefusal, match="page"):
        refuse_commissioning_page("the machine is commissioned")


def test_proof_earns_the_continuity_key() -> None:
    assert "control_files_and_checkpoint_current" in prove_session_15()
    assert "control_files_and_checkpoint_current" in EARNED_EVIDENCE_KEYS
