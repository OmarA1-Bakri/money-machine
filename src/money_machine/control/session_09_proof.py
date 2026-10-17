"""Earn Session 09 keys from in-memory fixtures and the control checkpoint.

The proof does not open a socket, publish a listing, read the ramp file,
or commission an agent.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

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
from money_machine.integrations.etsy.draft_client import (
    DraftLedger,
    DraftSpec,
    EtsyDraftClient,
    EtsyDraftRefused,
    FixtureCall,
    draft_marker,
    fixture_hash,
)

PREFLIGHT_EVIDENCE_KEY = "etsy_preflight_implemented"
RAMP_EVIDENCE_KEY = "publishing_ramp_implemented"
RECEIPT_EVIDENCE_KEY = "mutation_receipt_implemented"
DRAFT_EVIDENCE_KEY = "fixture_draft_package_implemented"
CONTROL_EVIDENCE_KEY = "control_files_and_checkpoint_current"
EARNED_EVIDENCE_KEYS = frozenset(
    {
        PREFLIGHT_EVIDENCE_KEY,
        RAMP_EVIDENCE_KEY,
        RECEIPT_EVIDENCE_KEY,
        DRAFT_EVIDENCE_KEY,
        CONTROL_EVIDENCE_KEY,
    }
)
_PRODUCT = UUID("00000000-0000-4000-8000-0000000000a8")
_LISTINGS = "/v3/application/shops/123456/listings"
_CONTROL_FILES = (
    Path("docs/control/IMPLEMENTATION_STATE.json"),
    Path("docs/control/IMPLEMENTATION_LOG.md"),
    Path("docs/control/DECISIONS.md"),
    Path("docs/control/TEST_EVIDENCE.md"),
    Path("docs/control/NEXT_SESSION.md"),
    Path("docs/control/SESSION_EVIDENCE.md"),
)
_BEHAVIORAL_KEYS = (
    PREFLIGHT_EVIDENCE_KEY,
    RAMP_EVIDENCE_KEY,
    RECEIPT_EVIDENCE_KEY,
    DRAFT_EVIDENCE_KEY,
)
_SESSION_10_KEYS = frozenset(
    {
        "metrics_fixture_implemented",
        "maturity_clock_implemented",
        "portfolio_eligibility_implemented",
        "closed_loop_store_implemented",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
_SESSION_11_KEYS = frozenset(
    {
        "support_intake_implemented",
        "incident_routing_implemented",
        "repair_resolution_implemented",
        "draft_reply_implemented",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
_SESSION_12_KEYS = frozenset(
    {
        "console_read_model_implemented",
        "exception_views_implemented",
        "telemetry_redaction_implemented",
        "operator_actions_fail_closed",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
_SESSION_13_KEYS = frozenset(
    {
        "implementation_matrix_recorded",
        "synthetic_paths_implemented",
        "failure_injection_implemented",
        "backup_restore_fixture_implemented",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
_SESSION_12_CLOSURE = "d81db61033561bdd40869ff1316f0c935c74cdf4"
_SESSION_13_CLOSURE = "fbaf8e8bdd73b1e3b6fa4f87158574057b72d18a"
_SESSION_13_PROMPT = "16_SESSION_13_E2E_HARDENING_AND_FAILURE_RECOVERY.md"
_SESSION_14_PROMPT = "17_SESSION_14_DEPLOYMENT.md"
_SESSION_14_KEYS = frozenset(
    {
        "deployment_target_recorded",
        "production_packaging_defined",
        "release_rollback_implemented",
        "service_controls_fail_closed",
        "control_files_and_checkpoint_current",
        "evidence_closure_commit_recorded",
    }
)
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
    _prove_draft_package()
    _prove_control_files()
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


class _DraftShop:
    """In-memory shop. It records calls and does not open a socket."""

    def __init__(self, listings: list[dict[str, object]] | None = None) -> None:
        self.listings = [] if listings is None else list(listings)
        self.calls: list[FixtureCall] = []
        self.posts = 0

    def exchange(self, call: FixtureCall) -> Mapping[str, object]:
        self.calls.append(call)
        if call.method == "GET":
            state = dict(call.query).get("state", "active")
            matched = [row for row in self.listings if row.get("state") == state]
            return {"count": len(matched), "results": matched}
        if call.method != "POST" or call.body is None:
            raise Session09ProofError("draft_method")
        fields = dict(call.body)
        self.posts += 1
        row: dict[str, object] = {
            "listing_id": 5000 + self.posts,
            "title": fields["title"],
            "description": fields["description"],
            "state": "draft",
        }
        self.listings.append(row)
        return row


class _ActiveShop:
    """Returns one active row on every read. A post is a proof failure."""

    def __init__(self, row: dict[str, object]) -> None:
        self.row = row
        self.posts = 0

    def exchange(self, call: FixtureCall) -> Mapping[str, object]:
        if call.method == "GET":
            return {"count": 1, "results": [self.row]}
        self.posts += 1
        raise Session09ProofError("draft_active_post")


def _prove_draft_package() -> None:
    public = {name for name in dir(EtsyDraftClient) if not name.startswith("_")}
    if {"publish", "activate", "update_listing"} & public or "create_draft" not in public:
        raise Session09ProofError("draft_publish_method")
    with tempfile.TemporaryDirectory() as directory:
        shop = _DraftShop()
        client = EtsyDraftClient(shop, DraftLedger(Path(directory)))
        spec = _draft_spec()
        receipt = client.create_draft(spec)
        marker = draft_marker(spec.spec_version, fixture_hash(spec))
        if receipt.state != "draft" or receipt.ready is not True:
            raise Session09ProofError("draft_package")
        if receipt.marker != marker or shop.posts != 1:
            raise Session09ProofError("draft_package")
        posts = [call for call in shop.calls if call.method == "POST"]
        gets = [call for call in shop.calls if call.method == "GET"]
        if len(posts) != 1 or len(gets) != 2 or posts[0].body is None:
            raise Session09ProofError("draft_package")
        fields = dict(posts[0].body)
        if "state" in fields or fields.get("type") != "download":
            raise Session09ProofError("draft_package")
        if not str(fields.get("description", "")).endswith(marker):
            raise Session09ProofError("draft_package")
        calls = len(shop.calls)
        again = client.create_draft(spec)
        if again.listing_id != receipt.listing_id or shop.posts != 1 or len(shop.calls) != calls:
            raise Session09ProofError("draft_retry")
        active = _ActiveShop(
            {
                "listing_id": 9,
                "title": spec.title,
                "description": f"{spec.description}\n{marker}",
                "state": "active",
            }
        )
        try:
            EtsyDraftClient(active, DraftLedger(Path(directory) / "active")).create_draft(spec)
        except EtsyDraftRefused as error:
            if error.code != "active" or active.posts != 0:
                raise Session09ProofError("draft_active") from error
        else:
            raise Session09ProofError("draft_active")
        blocked = _DraftShop()
        try:
            EtsyDraftClient(blocked, DraftLedger(Path(directory) / "blocked")).exchange(
                "PATCH",
                _LISTINGS,
                (),
                (("state", "active"),),
            )
        except EtsyDraftRefused as error:
            if error.code != "off_list" or blocked.calls:
                raise Session09ProofError("draft_off_list") from error
        else:
            raise Session09ProofError("draft_off_list")
        try:
            EtsyDraftClient(None, DraftLedger(Path(directory) / "bare")).create_draft(spec)
        except EtsyDraftRefused as error:
            if error.code != "fixture_transport":
                raise Session09ProofError("draft_transport") from error
        else:
            raise Session09ProofError("draft_transport")


def _draft_spec() -> DraftSpec:
    return DraftSpec(
        product_id=_PRODUCT,
        spec_version=2,
        shop_id=123456,
        title="Fixture planner",
        description="A fixture description.",
        price="11.00",
        quantity=999,
        who_made="i_did",
        when_made="2020_2026",
        taxonomy_id=1,
    )


def _draft(quantity: int, claim: PreflightClaim) -> EtsyPreflightDraft:
    return EtsyPreflightDraft(
        quantity=quantity,
        tags=_TAGS,
        images=_IMAGES,
        videos=1,
        claims=(claim,),
    )


def _prove_control_files() -> None:
    root = Path(__file__).resolve().parents[3]
    for relative in _CONTROL_FILES:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            raise Session09ProofError("control_files")
    # session_evidence imports state, and state imports this module.
    from money_machine.control.session_evidence import render_session_evidence

    catalogue = root / "docs/control/SESSION_EVIDENCE.md"
    if catalogue.read_text(encoding="utf-8") != render_session_evidence():
        raise Session09ProofError("control_checkpoint")
    decoded: object = json.loads(
        (root / "docs/control/IMPLEMENTATION_STATE.json").read_text(encoding="utf-8")
    )
    if not isinstance(decoded, dict):
        raise Session09ProofError("control_checkpoint")
    evidence = decoded.get("required_completion_evidence")
    status = decoded.get("session_status")
    if decoded.get("current_session") == 14:
        _prove_activated_session_14(decoded, evidence, status)
        return
    if decoded.get("current_session") == 13:
        _prove_activated_session_13(decoded, evidence, status)
        return
    if decoded.get("current_session") == 12:
        _prove_activated_session_12(decoded, evidence, status)
        return
    if decoded.get("current_session") == 11:
        _prove_activated_session_11(decoded, evidence, status)
        return
    if decoded.get("current_session") == 10:
        _prove_activated_session_10(decoded, evidence, status)
        return
    if (
        decoded.get("current_session") != 9
        or decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or not isinstance(evidence, dict)
        or status not in {"incomplete", "complete"}
    ):
        raise Session09ProofError("control_checkpoint")
    for key in _BEHAVIORAL_KEYS:
        if evidence.get(key) is not True:
            raise Session09ProofError("control_checkpoint")
    closure_recorded = evidence.get("evidence_closure_commit_recorded")
    if status == "incomplete":
        if closure_recorded is not False:
            raise Session09ProofError("control_checkpoint")
        return
    if closure_recorded is not True or evidence.get(CONTROL_EVIDENCE_KEY) is not True:
        raise Session09ProofError("control_checkpoint")
    if decoded.get("next_session") != 10 or decoded.get("completed_sessions") != list(range(10)):
        raise Session09ProofError("control_checkpoint")


def _prove_activated_session_10(
    decoded: Mapping[str, object],
    evidence: object,
    status: object,
) -> None:
    """Session 09 stays closed while Session 10 is incomplete or complete."""
    recorded: set[str] = set()
    values_are_bool = False
    evidence_count = -1
    if isinstance(evidence, dict):
        evidence_count = len(evidence)
        for key in evidence:
            if isinstance(key, str):
                recorded.add(key)
        values_are_bool = all(isinstance(value, bool) for value in evidence.values())
    keys_match = frozenset(recorded) == _SESSION_10_KEYS and len(recorded) == evidence_count
    if (
        decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or not keys_match
        or not values_are_bool
    ):
        raise Session09ProofError("control_checkpoint")
    if status == "incomplete":
        if decoded.get("next_session") != 10 or decoded.get("completed_sessions") != list(
            range(10)
        ):
            raise Session09ProofError("control_checkpoint")
        return
    if status != "complete" or not isinstance(evidence, dict):
        raise Session09ProofError("control_checkpoint")
    if (
        decoded.get("next_session") != 11
        or decoded.get("completed_sessions") != list(range(11))
        or any(value is not True for value in evidence.values())
    ):
        raise Session09ProofError("control_checkpoint")


def _prove_activated_session_11(
    decoded: Mapping[str, object],
    evidence: object,
    status: object,
) -> None:
    """Session 09 stays closed while Session 11 is incomplete or complete."""
    recorded: set[str] = set()
    values_are_bool = False
    evidence_count = -1
    if isinstance(evidence, dict):
        evidence_count = len(evidence)
        for key in evidence:
            if isinstance(key, str):
                recorded.add(key)
        values_are_bool = all(isinstance(value, bool) for value in evidence.values())
    keys_match = frozenset(recorded) == _SESSION_11_KEYS and len(recorded) == evidence_count
    if (
        decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or not keys_match
        or not values_are_bool
    ):
        raise Session09ProofError("control_checkpoint")
    if status == "incomplete":
        if decoded.get("next_session") != 11 or decoded.get("completed_sessions") != list(
            range(11)
        ):
            raise Session09ProofError("control_checkpoint")
        return
    if status != "complete" or not isinstance(evidence, dict):
        raise Session09ProofError("control_checkpoint")
    if (
        decoded.get("next_session") != 12
        or decoded.get("completed_sessions") != list(range(12))
        or decoded.get("next_prompt") != "15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md"
        or any(value is not True for value in evidence.values())
    ):
        raise Session09ProofError("control_checkpoint")


def _prove_activated_session_12(
    decoded: Mapping[str, object],
    evidence: object,
    status: object,
) -> None:
    """Session 09 stays closed while Session 12 is incomplete or complete."""
    recorded: set[str] = set()
    values_are_bool = False
    evidence_count = -1
    if isinstance(evidence, dict):
        evidence_count = len(evidence)
        for key in evidence:
            if isinstance(key, str):
                recorded.add(key)
        values_are_bool = all(isinstance(value, bool) for value in evidence.values())
    keys_match = frozenset(recorded) == _SESSION_12_KEYS and len(recorded) == evidence_count
    if (
        decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or not keys_match
        or not values_are_bool
    ):
        raise Session09ProofError("control_checkpoint")
    if status == "incomplete":
        if (
            decoded.get("next_session") != 12
            or decoded.get("completed_sessions") != list(range(12))
            or decoded.get("next_prompt") != "15_SESSION_12_OPERATOR_CONSOLE_AND_POSTHOG.md"
        ):
            raise Session09ProofError("control_checkpoint")
        return
    if status != "complete" or not isinstance(evidence, dict):
        raise Session09ProofError("control_checkpoint")
    if (
        decoded.get("next_session") != 13
        or decoded.get("completed_sessions") != list(range(13))
        or decoded.get("next_prompt") != _SESSION_13_PROMPT
        or any(value is not True for value in evidence.values())
    ):
        raise Session09ProofError("control_checkpoint")


def _prove_activated_session_13(
    decoded: Mapping[str, object],
    evidence: object,
    status: object,
) -> None:
    """Session 09 stays closed while Session 13 is complete."""
    recorded: set[str] = set()
    values_are_bool = False
    evidence_count = -1
    if isinstance(evidence, dict):
        evidence_count = len(evidence)
        for key in evidence:
            if isinstance(key, str):
                recorded.add(key)
        values_are_bool = all(isinstance(value, bool) for value in evidence.values())
    keys_match = frozenset(recorded) == _SESSION_13_KEYS and len(recorded) == evidence_count
    if (
        decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or decoded.get("head_sha") != _SESSION_13_CLOSURE
        or not keys_match
        or not values_are_bool
        or not isinstance(evidence, dict)
        or status != "complete"
        or decoded.get("next_session") != 14
        or decoded.get("completed_sessions") != list(range(14))
        or decoded.get("next_prompt") != _SESSION_14_PROMPT
        or any(value is not True for value in evidence.values())
    ):
        raise Session09ProofError("control_checkpoint")


def _prove_activated_session_14(
    decoded: Mapping[str, object],
    evidence: object,
    status: object,
) -> None:
    """Session 09 stays closed while Session 14 is incomplete and every key is false."""
    recorded: set[str] = set()
    values_are_bool = False
    evidence_count = -1
    if isinstance(evidence, dict):
        evidence_count = len(evidence)
        for key in evidence:
            if isinstance(key, str):
                recorded.add(key)
        values_are_bool = all(isinstance(value, bool) for value in evidence.values())
    keys_match = frozenset(recorded) == _SESSION_14_KEYS and len(recorded) == evidence_count
    if (
        decoded.get("head_sha") != decoded.get("evidence_closure_commit_sha")
        or decoded.get("head_sha") != _SESSION_13_CLOSURE
        or not keys_match
        or not values_are_bool
        or not isinstance(evidence, dict)
        or status != "incomplete"
        or decoded.get("next_session") != 14
        or decoded.get("completed_sessions") != list(range(14))
        or decoded.get("next_prompt") != _SESSION_14_PROMPT
        or any(value is not False for value in evidence.values())
    ):
        raise Session09ProofError("control_checkpoint")
