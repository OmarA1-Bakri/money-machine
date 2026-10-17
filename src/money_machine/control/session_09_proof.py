"""Earn Session 09 preflight and ramp keys from in-memory fixtures.

The proof does not open a socket, publish a listing, read the ramp file,
or commission an agent.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from money_machine.assets.etsy_preflight import (
    EtsyPreflightDraft,
    PreflightBlocked,
    PreflightClaim,
    run_etsy_preflight,
)
from money_machine.assets.publishing_ramp_decision import decide_publishing_ramp
from money_machine.domain.enums import BranchOutcome
from money_machine.domain.models.listings import PreflightResult

PREFLIGHT_EVIDENCE_KEY = "etsy_preflight_implemented"
RAMP_EVIDENCE_KEY = "publishing_ramp_implemented"
EARNED_EVIDENCE_KEYS = frozenset({PREFLIGHT_EVIDENCE_KEY, RAMP_EVIDENCE_KEY})
_OLDEST = datetime(2026, 10, 9, 15, 30, tzinfo=UTC)
_TAGS = tuple(f"tag {number}" for number in range(1, 14))
_IMAGES = (
    "hero",
    "overview",
    "hub_1",
    "hub_2",
    "hub_3",
    "hub_4",
    "hub_5",
    "colour_options",
    "devices",
    "how_it_works",
)


class Session09ProofError(ValueError):
    """The preflight fixture did not earn its evidence key."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def prove_session_09() -> frozenset[str]:
    """Return the one key the checklist earns. A miss raises instead of returning it."""
    passed = run_etsy_preflight(_draft(999, PreflightClaim("Includes six hubs", "fact:hubs")))
    if not isinstance(passed, PreflightResult) or passed.outcome is not BranchOutcome.PASS:
        raise Session09ProofError("preflight_pass")
    if passed.repair_job_types:
        raise Session09ProofError("preflight_repair")
    failed = run_etsy_preflight(_draft(998, PreflightClaim("Includes six hubs", "fact:hubs")))
    if not isinstance(failed, PreflightResult) or failed.outcome is not BranchOutcome.FAIL:
        raise Session09ProofError("preflight_fail")
    if failed.repair_job_types != ("repair_quantity",):
        raise Session09ProofError("preflight_repair_job")
    blocked = run_etsy_preflight(_draft(999, PreflightClaim("Includes six hubs", None)))
    if not isinstance(blocked, PreflightBlocked) or blocked.repair_job_types:
        raise Session09ProofError("preflight_block")
    _prove_ramp()
    return EARNED_EVIDENCE_KEYS


def _prove_ramp() -> None:
    disabled = decide_publishing_ramp(
        publishing_enabled=False,
        initial_weekly_cap=2,
        hard_weekly_cap=15,
        rolling_window_days=7,
        reconciled_count=0,
        oldest_reconciled_at=None,
        unreconciled_count=0,
    )
    if disabled.may_publish or disabled.next_permissible_at is not None:
        raise Session09ProofError("ramp_disabled")
    at_cap = decide_publishing_ramp(
        publishing_enabled=True,
        initial_weekly_cap=2,
        hard_weekly_cap=15,
        rolling_window_days=7,
        reconciled_count=2,
        oldest_reconciled_at=_OLDEST,
        unreconciled_count=0,
    )
    if at_cap.may_publish or at_cap.next_permissible_at != _OLDEST + timedelta(days=7):
        raise Session09ProofError("ramp_at_cap")
    below = decide_publishing_ramp(
        publishing_enabled=True,
        initial_weekly_cap=2,
        hard_weekly_cap=15,
        rolling_window_days=7,
        reconciled_count=1,
        oldest_reconciled_at=_OLDEST,
        unreconciled_count=1,
    )
    if not below.may_publish or below.next_permissible_at is not None:
        raise Session09ProofError("ramp_below_cap")
    supplied = decide_publishing_ramp(
        publishing_enabled=True,
        initial_weekly_cap=3,
        hard_weekly_cap=15,
        rolling_window_days=7,
        reconciled_count=2,
        oldest_reconciled_at=_OLDEST,
        unreconciled_count=0,
    )
    if not supplied.may_publish:
        raise Session09ProofError("ramp_supplied_cap")
    hard = decide_publishing_ramp(
        publishing_enabled=True,
        initial_weekly_cap=16,
        hard_weekly_cap=15,
        rolling_window_days=7,
        reconciled_count=15,
        oldest_reconciled_at=_OLDEST,
        unreconciled_count=0,
    )
    if hard.may_publish:
        raise Session09ProofError("ramp_hard_cap")


def _draft(quantity: int, claim: PreflightClaim) -> EtsyPreflightDraft:
    return EtsyPreflightDraft(
        quantity=quantity,
        tags=_TAGS,
        images=_IMAGES,
        videos=1,
        claims=(claim,),
    )
