"""Earn the Session 09 preflight key from the in-memory checklist.

The proof does not open a socket, publish a listing, or commission an agent.
"""

from __future__ import annotations

from money_machine.assets.etsy_preflight import (
    EtsyPreflightDraft,
    PreflightBlocked,
    PreflightClaim,
    run_etsy_preflight,
)
from money_machine.domain.enums import BranchOutcome
from money_machine.domain.models.listings import PreflightResult

PREFLIGHT_EVIDENCE_KEY = "etsy_preflight_implemented"
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
    return frozenset({PREFLIGHT_EVIDENCE_KEY})


def _draft(quantity: int, claim: PreflightClaim) -> EtsyPreflightDraft:
    return EtsyPreflightDraft(
        quantity=quantity,
        tags=_TAGS,
        images=_IMAGES,
        videos=1,
        claims=(claim,),
    )
