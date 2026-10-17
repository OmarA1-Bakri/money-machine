"""Earn Session 09 preflight, ramp, and receipt keys from in-memory fixtures.

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
from money_machine.assets.mutation_receipt import (
    ListingMutation,
    ReadObservation,
    ReceiptBook,
    ReceiptRejected,
    WriteTimeout,
    build_receipt,
    commit_listing_mutation,
)
from money_machine.assets.publishing_ramp_decision import decide_publishing_ramp
from money_machine.domain.enums import BranchOutcome
from money_machine.domain.models.listings import PreflightResult

PREFLIGHT_EVIDENCE_KEY = "etsy_preflight_implemented"
RAMP_EVIDENCE_KEY = "publishing_ramp_implemented"
RECEIPT_EVIDENCE_KEY = "mutation_receipt_implemented"
EARNED_EVIDENCE_KEYS = frozenset({PREFLIGHT_EVIDENCE_KEY, RAMP_EVIDENCE_KEY, RECEIPT_EVIDENCE_KEY})
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
    """The Session 09 fixture did not earn its evidence keys."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def prove_session_09() -> frozenset[str]:
    """Return the keys the checklist has earned. A miss raises instead of returning them."""
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
    _prove_receipt()
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


class _ReceiptDouble:
    """In-memory listing double. It records creates and does not open a socket."""

    def __init__(
        self,
        *,
        timeout: bool = False,
        visible: dict[str, str] | None = None,
        unknown: bool = False,
    ) -> None:
        self.timeout = timeout
        self.visible = dict(visible or {})
        self.unknown = unknown
        self.creates: list[str] = []
        self._attempted = 0

    def create(self, idempotency_key: str) -> str:
        self._attempted += 1
        if self.timeout and self._attempted == 1:
            raise WriteTimeout(idempotency_key)
        provider_id = f"listing-{len(self.creates) + 1}"
        self.creates.append(idempotency_key)
        self.visible[idempotency_key] = provider_id
        return provider_id

    def read(self, idempotency_key: str) -> ReadObservation:
        if self.unknown:
            return ReadObservation(observed=True, provider_id=None, unknown=True)
        return ReadObservation(
            observed=True,
            provider_id=self.visible.get(idempotency_key),
            unknown=False,
        )


def _prove_receipt() -> None:
    same = _ReceiptDouble()
    book = ReceiptBook()
    mutation = _listing_mutation("key-a")
    first = commit_listing_mutation(book, same, mutation)
    second = commit_listing_mutation(book, same, mutation)
    if same.creates != ["key-a"] or first.provider_id != second.provider_id:
        raise Session09ProofError("receipt_same_key")
    found = _ReceiptDouble(timeout=True, visible={"key-a": "listing-found"})
    found_receipt = commit_listing_mutation(ReceiptBook(), found, mutation)
    if found.creates or found_receipt.provider_id != "listing-found":
        raise Session09ProofError("receipt_timeout_found")
    absent = _ReceiptDouble(timeout=True)
    absent_receipt = commit_listing_mutation(ReceiptBook(), absent, mutation)
    if absent.creates != ["key-a"] or absent_receipt.effect_state != "CONFIRMED":
        raise Session09ProofError("receipt_timeout_absent")
    unknown_double = _ReceiptDouble(timeout=True, unknown=True)
    unknown_book = ReceiptBook()
    unknown = commit_listing_mutation(unknown_book, unknown_double, mutation)
    again = commit_listing_mutation(unknown_book, unknown_double, mutation)
    if unknown.effect_state != "UNKNOWN" or unknown_double.creates or again is not unknown:
        raise Session09ProofError("receipt_unknown")
    try:
        build_receipt(
            operation="etsy.create_draft",
            listing_target="shop:1/listing",
            pre_state="absent",
            expected_post_state="draft",
            provider_id="listing-1",
            response_hash=None,
            idempotency_key="key-a",
            effect_state="CONFIRMED",
        )
    except ReceiptRejected:
        pass
    else:
        raise Session09ProofError("receipt_hash")
    try:
        build_receipt(
            operation="etsy.create_draft",
            listing_target="shop:1/listing",
            pre_state="absent",
            expected_post_state="draft",
            provider_id="listing-1",
            response_hash="ab" * 32,
            idempotency_key="key-a",
            effect_state="CONFIRMED",
            screenshot="pixels",
        )
    except ReceiptRejected:
        pass
    else:
        raise Session09ProofError("receipt_screenshot")
    try:
        build_receipt(
            operation="etsy.create_draft",
            listing_target="shop:1/listing",
            pre_state="absent",
            expected_post_state="draft",
            provider_id="listing-1",
            response_hash="ab" * 32,
            idempotency_key="key-a",
            effect_state="CONFIRMED",
            response={"listing_id": 1},
        )
    except ReceiptRejected:
        return
    raise Session09ProofError("receipt_raw_body")


def _listing_mutation(key: str) -> ListingMutation:
    return ListingMutation(
        operation="etsy.create_draft",
        listing_target="shop:1/listing",
        pre_state="absent",
        expected_post_state="draft",
        idempotency_key=key,
    )


def _draft(quantity: int, claim: PreflightClaim) -> EtsyPreflightDraft:
    return EtsyPreflightDraft(
        quantity=quantity,
        tags=_TAGS,
        images=_IMAGES,
        videos=1,
        claims=(claim,),
    )
