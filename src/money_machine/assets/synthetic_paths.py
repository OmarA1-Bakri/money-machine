"""Fixture-backed product paths. No live provider call.

The main chain builds a research report, a product spec, a passing dedupe, a
Notion build artifact, QA, variants, listing copy, assets, PDFs, an Etsy draft
through the fixture client, preflight, a refused live publish, weekly metrics,
a thirty-day maturity clock, a winner, a successor spec, and a successor build
job. Cull, repair, broken-link, and too-close dedupe are separate receipts.
"""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import JsonValue

from money_machine.agents.contracts.merchandising import IMAGE_ROLES
from money_machine.assets.asset_lineage import BoundAsset, fixture_storage_uri
from money_machine.assets.closed_loop_store import (
    TriggerLedger,
    confirm_fixture_cull,
    persist_weekly_plan,
)
from money_machine.assets.etsy_draft import DraftEvidence, DraftGateError, prepare_etsy_draft
from money_machine.assets.etsy_preflight import (
    EtsyPreflightDraft,
    PreflightBlocked,
    PreflightClaim,
    run_etsy_preflight,
)
from money_machine.assets.maturity_clock import LiveInterval, evaluate_maturity
from money_machine.assets.metrics_fixture import ActiveListing, plan_weekly, snapshots_from_fixture
from money_machine.assets.portfolio_eligibility import (
    ListingCandidate,
    PortfolioResult,
    SnapshotView,
    evaluate_portfolio,
    is_successful_result,
)
from money_machine.assets.support_intake import (
    IntakeLedger,
    VerificationRead,
    draft_reply,
    open_issue,
    record_repair,
    resolve_issue,
)
from money_machine.domain.enums import BranchOutcome, DecisionType
from money_machine.domain.events import EventName
from money_machine.domain.models.common import ArtifactReference, CheckResult, EvidenceReference
from money_machine.domain.models.products import (
    BuildResult,
    ProductQAResult,
    ProductSpec,
    ResearchObservation,
    ResearchReport,
    TeardownReport,
)
from money_machine.domain.models.rules import ProductShapeRules
from money_machine.domain.services.dedupe import check_dedupe
from money_machine.integrations.etsy.draft_client import (
    DraftLedger,
    DraftReceipt,
    EtsyDraftClient,
    FixtureCall,
)

MAIN_STEPS: tuple[str, ...] = (
    "research",
    "shortlist",
    "score",
    "teardown",
    "product_spec",
    "dedupe",
    "notion_build",
    "qa",
    "variants",
    "listing_copy",
    "assets",
    "pdfs",
    "etsy_draft",
    "preflight",
    "publish_simulation",
    "post_publish_verification",
    "weekly_metrics",
    "thirty_day_maturity",
    "winner",
    "successor_product_spec",
    "successor_build_job",
)
CULL_STEPS: tuple[str, ...] = ("mature_loser", "cull_decision", "deactivation", "lesson")
REPAIR_STEPS: tuple[str, ...] = (
    "mature_conversion_problem",
    "listing_repair",
    "updated_version",
    "observation",
)
BROKEN_LINK_STEPS: tuple[str, ...] = (
    "buyer_issue",
    "incident",
    "reproduce",
    "source_repair",
    "listing_file_replacement",
    "verify",
    "response",
)
DEDUPE_STEPS: tuple[str, ...] = ("too_close_product_spec", "reconcept", "pass", "build")

_WHEN = datetime(2026, 10, 16, tzinfo=UTC)
_PUBLISHED = datetime(2026, 8, 1, tzinfo=UTC)
_NAMESPACE = uuid5(NAMESPACE_URL, "https://money-machine.invalid/synthetic-paths")
_RULE_VERSION = "1.0.0"
_FIXTURE_LISTING_ID = 9001
_SHOP_NUMERIC = 1001
_HUBS = ("Daily", "Goals", "Habits", "Budget", "Meals", "Fitness")
_COLOURS = ("Sage", "Navy", "Rose")
_FEATURES = ("Hyperlinks", "Checkboxes", "Calendar", "Weekly spreads")
_TAGS = _HUBS + _COLOURS + _FEATURES


class SyntheticPathRefusal(ValueError):
    """A fixture path refused to continue."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True, slots=True)
class PathReceipt:
    """One persisted step. The artifact id is stable across runs."""

    path: str
    step: str
    artifact_id: UUID
    outcome: str


@dataclass(frozen=True, slots=True)
class PublishSimulation:
    """A publish that was not sent. ``executed`` stays false."""

    mode: Literal["simulation"]
    executed: bool
    provider_called: bool
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class SyntheticRun:
    """Every path receipt from one fixture run. Nothing here was published live."""

    receipts: tuple[PathReceipt, ...]
    published_live: bool


@dataclass(frozen=True, slots=True)
class _ListingCopy:
    title: str
    description: str
    tags: tuple[str, ...]
    price: str


class _MemoryShop:
    """Stand-in for the Etsy draft transport. It answers from memory."""

    def exchange(self, call: FixtureCall) -> Mapping[str, object]:
        if call.method == "GET":
            return {"count": 0, "results": []}
        body = dict(call.body or ())
        return {
            "state": "draft",
            "listing_id": _FIXTURE_LISTING_ID,
            "description": body.get("description", ""),
        }


def _json_int(mapping: Mapping[str, JsonValue], field: str) -> int:
    """Coerce a JSON-backed research fact to an int for fixture scoring."""
    value = mapping.get(field)
    if isinstance(value, bool):
        raise TypeError(f"{field} fact is boolean, not an int-like value")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"{field} fact is not int-like: {type(value).__name__}")


def simulate_publish(
    *,
    mode: Literal["simulation", "live"],
    idempotency_key: str,
) -> PublishSimulation:
    """Return one unsent receipt. ``live`` is refused before any provider call."""
    if mode == "live":
        raise SyntheticPathRefusal("live_publish")
    return PublishSimulation(
        mode="simulation",
        executed=False,
        provider_called=False,
        idempotency_key=idempotency_key,
    )


def run_synthetic_paths() -> SyntheticRun:
    """Run the main chain and the four alternate paths. A second call matches."""
    receipts = (
        *_main_path(),
        *_cull_path(),
        *_repair_path(),
        *_broken_link_path(),
        *_dedupe_path(),
    )
    _require("main", receipts, MAIN_STEPS)
    _require("cull", receipts, CULL_STEPS)
    _require("repair", receipts, REPAIR_STEPS)
    _require("broken_link", receipts, BROKEN_LINK_STEPS)
    _require("dedupe", receipts, DEDUPE_STEPS)
    return SyntheticRun(receipts=receipts, published_live=False)


def _main_path() -> tuple[PathReceipt, ...]:
    report = _research_report()
    shortlist = _shortlist(report)
    winner_observation = _score(shortlist)
    teardown = _teardown(winner_observation)
    spec = _original_spec(teardown)
    passed = check_dedupe(spec, [_catalogue_spec()], _RULE_VERSION)
    if passed.outcome is not BranchOutcome.PASS:
        raise SyntheticPathRefusal("dedupe")
    build = _notion_build(spec)
    qa = _qa(build)
    variants = _variants(spec, build)
    copy = _listing_copy(spec)
    assets = _assets(spec)
    pdfs = tuple(asset for asset in assets if asset.kind == "delivery_pdf")
    draft = _etsy_draft(spec, copy, assets)
    preflight = _preflight(copy, assets)
    publish = simulate_publish(mode="simulation", idempotency_key=f"publish:{spec.spec_id}")
    repeated = simulate_publish(mode="simulation", idempotency_key=publish.idempotency_key)
    if publish != repeated or publish.executed or publish.provider_called:
        raise SyntheticPathRefusal("publish_simulation")
    metrics = _weekly()
    maturity = evaluate_maturity(
        listing_id=_stable("listing"),
        published_at=_PUBLISHED,
        intervals=(LiveInterval("ACTIVE", _PUBLISHED, _WHEN),),
        evaluated_at=_WHEN,
        live_days=0,
    )
    if not maturity.mature or not maturity.portfolio_decision_due:
        raise SyntheticPathRefusal("maturity")
    portfolio = _winner_listing(spec)
    results = evaluate_portfolio((portfolio,), decided_at=_WHEN)
    if len(results) != 1 or not is_successful_result(results[0]):
        raise SyntheticPathRefusal("winner")
    successor = _successor_spec(spec, results[0])
    successor_dedupe = check_dedupe(successor, [spec], _RULE_VERSION)
    if successor_dedupe.outcome is not BranchOutcome.PASS:
        raise SyntheticPathRefusal("successor_dedupe")
    successor_build = _build_result(successor, "successor-build", "PRIMARY", ("build-slot",))
    return (
        _receipt("main", "research", report.report_id, "RECORDED"),
        _receipt("main", "shortlist", shortlist[0].observation_id, f"KEPT:{len(shortlist)}"),
        _receipt("main", "score", winner_observation.observation_id, "SELECTED"),
        _receipt("main", "teardown", teardown.report_id, "STRUCTURE_ONLY"),
        _receipt("main", "product_spec", spec.spec_id, spec.lineage_kind),
        _receipt("main", "dedupe", spec.spec_id, passed.outcome.value),
        _receipt("main", "notion_build", build.result_id, "FIXTURE"),
        _receipt("main", "qa", qa.result_id, qa.outcome.value),
        _receipt("main", "variants", variants.result_id, f"VARIANTS:{len(spec.colour_variants)}"),
        _receipt("main", "listing_copy", spec.spec_id, f"TAGS:{len(copy.tags)}"),
        _receipt("main", "assets", spec.product_id, f"ASSETS:{len(assets)}"),
        _receipt("main", "pdfs", pdfs[0].product_id, f"PDFS:{len(pdfs)}"),
        _receipt("main", "etsy_draft", spec.spec_id, f"DRAFT:{draft.listing_id}"),
        _receipt("main", "preflight", preflight.result_id, preflight.outcome.value),
        _receipt("main", "publish_simulation", spec.spec_id, "WITHHELD"),
        _receipt(
            "main",
            "post_publish_verification",
            spec.spec_id,
            "BLOCKED_BY_EXTERNAL_CREDENTIAL",
        ),
        _receipt("main", "weekly_metrics", metrics, "PLANNED"),
        _receipt("main", "thirty_day_maturity", _stable("listing"), "MATURE"),
        _receipt("main", "winner", results[0].decision_id, results[0].decision.value),
        _receipt("main", "successor_product_spec", successor.spec_id, successor.lineage_kind),
        _receipt("main", "successor_build_job", successor_build.result_id, "WITHHELD"),
    )


def _cull_path() -> tuple[PathReceipt, ...]:
    listings = _cull_cohort()
    results = evaluate_portfolio(listings, decided_at=_WHEN, cull_bottom_percent="40")
    culled = tuple(item for item in results if item.decision is DecisionType.CULL)
    if len(culled) != 1 or culled[0].deactivation_executed:
        raise SyntheticPathRefusal("cull")
    loser = culled[0]
    if loser.deactivation_job_id is None:
        raise SyntheticPathRefusal("deactivation")
    confirmation = confirm_fixture_cull(
        loser,
        fixture_status="CONFIRMED",
        lesson="The listing had no orders after thirty live days.",
        artifact_ids=(_stable("cull-artifact"),),
    )
    if (
        confirmation.deactivation_executed
        or EventName.LISTING_CULLED not in confirmation.event_names
        or confirmation.lesson is None
    ):
        raise SyntheticPathRefusal("lesson")
    return (
        _receipt("cull", "mature_loser", loser.listing_id, "MATURE"),
        _receipt("cull", "cull_decision", loser.decision_id, loser.decision.value),
        _receipt("cull", "deactivation", loser.deactivation_job_id, "UNEXECUTED"),
        _receipt("cull", "lesson", confirmation.lesson.listing_id, "RETAINED"),
    )


def _repair_path() -> tuple[PathReceipt, ...]:
    listing = _candidate(7, views=12, orders=0, revenue=0, favourites=1)
    results = evaluate_portfolio((listing,), decided_at=_WHEN)
    if len(results) != 1 or results[0].decision is not DecisionType.REPAIR:
        raise SyntheticPathRefusal("repair")
    repair = results[0]
    if repair.repair_job_id is None:
        raise SyntheticPathRefusal("listing_repair")
    observed = snapshots_from_fixture(
        (
            {
                "snapshot_id": _stable("repair-snapshot"),
                "listing_id": listing.listing_id,
                "listing_version": 2,
                "provider": "fixture",
                "observed_at": _WHEN,
                "views": 4,
                "favourites": 1,
                "orders": 1,
                "gross_revenue": Decimal("9.00"),
                "currency": "USD",
                "reconciled": True,
                "window_start": _WHEN - timedelta(days=7),
                "window_end": _WHEN,
                "evidence": _evidence("repair-observation"),
            },
        )
    )
    if observed[0].snapshot.orders < 1 or observed[0].snapshot.listing_version != 2:
        raise SyntheticPathRefusal("observation")
    return (
        _receipt("repair", "mature_conversion_problem", listing.listing_id, "NO_ORDERS"),
        _receipt("repair", "listing_repair", repair.repair_job_id, "REQUESTED"),
        _receipt("repair", "updated_version", listing.listing_id, "VERSION:2"),
        _receipt("repair", "observation", observed[0].snapshot.snapshot_id, "ORDERS:1"),
    )


def _broken_link_path() -> tuple[PathReceipt, ...]:
    ledger = IntakeLedger()
    opened = open_issue(
        ledger,
        shop_id=_stable("shop"),
        buyer_reference="buyer-fixture-1",
        listing_id=_stable("listing"),
        product_id=_stable("product"),
        variant_id=None,
        issue_code="BROKEN_DELIVERY_LINK",
        safe_summary="The delivery file link does not open.",
        attachment_sha256=_sha("broken-link-note"),
        attachment_content_type="text/plain",
        received_at=_WHEN,
        urgency="high",
    )
    again = open_issue(
        ledger,
        shop_id=opened.shop_id,
        buyer_reference=opened.buyer_reference,
        listing_id=opened.listing_id,
        product_id=opened.product_id,
        variant_id=None,
        issue_code="BROKEN_DELIVERY_LINK",
        safe_summary=opened.safe_summary,
        attachment_sha256=opened.attachment_sha256,
        attachment_content_type=opened.attachment_content_type,
        received_at=opened.received_at,
        urgency="high",
    )
    if again.incident_id != opened.incident_id or ledger.sends != 0:
        raise SyntheticPathRefusal("incident")
    digest = _sha("repaired-file")
    repair = record_repair(
        ledger,
        incident_id=opened.incident_id,
        idempotency_key="broken-link-repair",
        artifact_hash=digest,
    )
    read = VerificationRead(
        repair_job_id=repair.version_id,
        verification_job_id=_stable("verify-job"),
        repaired_hash=digest,
        fresh_hash=digest,
        repaired_at=_WHEN,
        read_at=_WHEN + timedelta(hours=1),
        fix="Replaced the delivery file.",
        access_path="delivery readme file",
    )
    resolution = resolve_issue(read)
    reply = draft_reply(ledger, read, mode="draft")
    if resolution.status != "RESOLVED" or reply.body is None or reply.send_count != 0:
        raise SyntheticPathRefusal("response")
    return (
        _receipt("broken_link", "buyer_issue", opened.incident_id, opened.issue_code),
        _receipt("broken_link", "incident", opened.incident_id, opened.incident_type.value),
        _receipt("broken_link", "reproduce", opened.incident_id, "LINK_MISSING"),
        _receipt("broken_link", "source_repair", repair.version_id, "REPAIRED"),
        _receipt("broken_link", "listing_file_replacement", repair.version_id, digest[:12]),
        _receipt("broken_link", "verify", read.verification_job_id, resolution.status),
        _receipt("broken_link", "response", opened.incident_id, "DRAFT"),
    )


def _dedupe_path() -> tuple[PathReceipt, ...]:
    catalogue = _catalogue_spec()
    close = _spec(
        "close",
        lineage="ORIGINAL",
        identity=catalogue.identity,
        category=catalogue.base_category,
        title=catalogue.title,
        problem=catalogue.buyer_problem,
        fingerprint=catalogue.concept_fingerprint,
    )
    refused = check_dedupe(close, [catalogue], _RULE_VERSION)
    if refused.outcome is not BranchOutcome.TOO_CLOSE or not refused.collisions:
        raise SyntheticPathRefusal("too_close")
    reconcept = _spec(
        "reconcept",
        lineage="RECONCEPT",
        identity="Kitchen closeout",
        category="Checklists",
        title="Kitchen closeout checklist",
        problem="Close the kitchen without a second full reset.",
        fingerprint=_sha("kitchen-closeout"),
        parent_spec_id=close.spec_id,
    )
    passed = check_dedupe(reconcept, [catalogue, close], _RULE_VERSION)
    if passed.outcome is not BranchOutcome.PASS:
        raise SyntheticPathRefusal("reconcept_pass")
    built = _build_result(reconcept, "reconcept-build", "PRIMARY", ("reconcept-build",))
    return (
        _receipt("dedupe", "too_close_product_spec", close.spec_id, refused.outcome.value),
        _receipt("dedupe", "reconcept", reconcept.spec_id, reconcept.lineage_kind),
        _receipt("dedupe", "pass", reconcept.spec_id, passed.outcome.value),
        _receipt("dedupe", "build", built.result_id, "BUILT"),
    )


def _research_report() -> ResearchReport:
    observations = tuple(
        ResearchObservation(
            observation_id=_stable(f"observation-{name}"),
            source_reference=f"fixture://research/{name}",
            observed_at=_WHEN,
            title=title,
            shop_reference=None,
            facts={"demand": demand},
            evidence=(_evidence(f"observation-{name}"),),
        )
        for name, title, demand in (
            ("low", "Spare sticker sheet", 1),
            ("mid", "Weekly meal cards", 4),
            ("high", "Household reset planner", 9),
        )
    )
    return ResearchReport(
        report_id=_stable("research-report"),
        workflow_id=_stable("workflow"),
        source_policy_version=_RULE_VERSION,
        query_terms=("planner", "reset"),
        observations=observations,
        summary_facts={"admitted": len(observations)},
        completed_at=_WHEN,
    )


def _shortlist(report: ResearchReport) -> tuple[ResearchObservation, ...]:
    kept = tuple(item for item in report.observations if _json_int(item.facts, "demand") >= 4)
    if len(kept) < 2:
        raise SyntheticPathRefusal("shortlist")
    return kept


def _score(shortlist: Sequence[ResearchObservation]) -> ResearchObservation:
    ranked = sorted(shortlist, key=lambda item: _json_int(item.facts, "demand"), reverse=True)
    best = ranked[0]
    if len(ranked) > 1 and _json_int(ranked[1].facts, "demand") == _json_int(best.facts, "demand"):
        raise SyntheticPathRefusal("score_tie")
    return best


def _teardown(observation: ResearchObservation) -> TeardownReport:
    return TeardownReport(
        report_id=_stable("teardown"),
        workflow_id=_stable("workflow"),
        competitor_reference=observation.source_reference,
        purchase_receipt_reference=None,
        structure_components=_HUBS,
        buyer_journey=("Open the listing", "Download the fixture", "Use the first hub"),
        mechanics=_FEATURES,
        copied_protected_content=False,
        source_evidence=observation.evidence,
        completed_at=_WHEN,
    )


def _original_spec(teardown: TeardownReport) -> ProductSpec:
    if teardown.copied_protected_content is not False:
        raise SyntheticPathRefusal("teardown_copy")
    if teardown.structure_components != _HUBS:
        raise SyntheticPathRefusal("teardown_shape")
    return _spec(
        "original",
        lineage="ORIGINAL",
        identity="Household reset",
        category="Planners",
        title="Household reset planner",
        problem="Reset the house without rebuilding the same list.",
        fingerprint=_sha("household-reset"),
    )


def _catalogue_spec() -> ProductSpec:
    return _spec(
        "catalogue",
        lineage="ORIGINAL",
        identity="Field notes",
        category="Cards",
        title="Field notes habit cards",
        problem="Keep one habit visible on a card.",
        fingerprint=_sha("field-notes"),
    )


def _successor_spec(parent: ProductSpec, winner: PortfolioResult) -> ProductSpec:
    if (
        winner.successor_spec_id is None
        or winner.successor_workflow_id is None
        or winner.parent_decision_id is None
        or winner.parent_workflow_id is None
    ):
        raise SyntheticPathRefusal("successor_lineage")
    return _spec(
        "successor",
        lineage="SUCCESSOR",
        identity="Seasonal pantry",
        category="Boards",
        title="Seasonal pantry reset board",
        problem="Reset the pantry once per season.",
        fingerprint=_sha("seasonal-pantry"),
        spec_id=winner.successor_spec_id,
        product_id=_stable("successor-product"),
        workflow_id=winner.successor_workflow_id,
        parent_spec_id=parent.spec_id,
        parent_product_id=parent.product_id,
        parent_decision_id=winner.parent_decision_id,
        parent_workflow_id=winner.parent_workflow_id,
    )


def _spec(
    name: str,
    *,
    lineage: Literal["ORIGINAL", "RECONCEPT", "SUCCESSOR"],
    identity: str,
    category: str,
    title: str,
    problem: str,
    fingerprint: str,
    spec_id: UUID | None = None,
    product_id: UUID | None = None,
    workflow_id: UUID | None = None,
    parent_spec_id: UUID | None = None,
    parent_product_id: UUID | None = None,
    parent_decision_id: UUID | None = None,
    parent_workflow_id: UUID | None = None,
) -> ProductSpec:
    return ProductSpec(
        spec_id=spec_id or _stable(f"spec-{name}"),
        workflow_id=workflow_id or _stable(f"workflow-{name}"),
        product_id=product_id or _stable(f"product-{name}"),
        version=1,
        lineage_kind=lineage,
        parent_spec_id=parent_spec_id,
        parent_product_id=parent_product_id,
        parent_decision_id=parent_decision_id,
        parent_workflow_id=parent_workflow_id,
        shape_rules=ProductShapeRules(
            rule_version=_RULE_VERSION,
            hubs_minimum=6,
            hubs_maximum=8,
            colour_variants_minimum=3,
            colour_variants_maximum=4,
        ),
        identity=identity,
        base_category=category,
        buyer_problem=problem,
        title=title,
        tier="mass",
        real_price=Decimal("8.99"),
        anchor_price=Decimal("14.99"),
        currency="USD",
        hubs=_HUBS,
        colour_variants=_COLOURS,
        features=_FEATURES,
        experiment_plan="Compare the first hub against the colour strip.",
        concept_fingerprint=fingerprint,
        source_evidence=(_evidence(f"spec-{name}"),),
        created_at=_WHEN,
    )


def _notion_build(spec: ProductSpec) -> BuildResult:
    return _build_result(spec, "notion-build", "PRIMARY", ("notion-pages",))


def _qa(build: BuildResult) -> ProductQAResult:
    artifact_id = build.artifacts[0].artifact_id
    return ProductQAResult(
        result_id=_stable("qa"),
        build_result_id=build.result_id,
        checked_artifact_ids=(artifact_id,),
        outcome=BranchOutcome.PASS,
        checks=(
            CheckResult(
                name="hubs",
                passed=True,
                evidence=(_evidence("qa-hubs"),),
                observed_value=len(_HUBS),
            ),
        ),
        defect_codes=(),
        evidence=(_evidence("qa"),),
        completed_at=_WHEN,
    )


def _variants(spec: ProductSpec, build: BuildResult) -> BuildResult:
    artifacts = tuple(
        _artifact(f"variant-{colour}", parent=(build.artifacts[0].artifact_id,))
        for colour in spec.colour_variants
    )
    return BuildResult(
        result_id=_stable("variants"),
        workflow_id=spec.workflow_id,
        product_id=spec.product_id,
        spec_id=spec.spec_id,
        build_version=1,
        build_kind="VARIANT",
        artifacts=artifacts,
        checkpoint_names=("colour-variants",),
        completed_at=_WHEN,
    )


def _listing_copy(spec: ProductSpec) -> _ListingCopy:
    if len(_TAGS) != 13:
        raise SyntheticPathRefusal("tags")
    return _ListingCopy(
        title=spec.title,
        description=spec.buyer_problem,
        tags=_TAGS,
        price=str(spec.real_price),
    )


def _assets(spec: ProductSpec) -> tuple[BoundAsset, ...]:
    shot = _bound(spec, "screenshot", "screenshot", ())
    images = tuple(
        _bound(spec, "listing_image", role, (shot.output_sha256,)) for role in IMAGE_ROLES
    )
    video = _bound(spec, "walkthrough", "walkthrough", (shot.output_sha256,))
    pdf_roles = ("readme", "free_gift")
    pdfs = tuple(_bound(spec, "delivery_pdf", role, (shot.output_sha256,)) for role in pdf_roles)
    return (shot, *images, video, *pdfs)


def _etsy_draft(
    spec: ProductSpec,
    copy: _ListingCopy,
    assets: tuple[BoundAsset, ...],
) -> DraftReceipt:
    evidence = DraftEvidence(
        product_id=spec.product_id,
        spec_version=spec.version,
        shop_id=_SHOP_NUMERIC,
        product_qa="passed",
        claims_passed=True,
        assets=assets,
        pdf_roles=("readme", "free_gift"),
        links_passed=True,
        title=copy.title,
        description=copy.description,
        price=copy.price,
        quantity=999,
        who_made="i_did",
        when_made="2020_2026",
        taxonomy_id=1,
    )
    try:
        with tempfile.TemporaryDirectory() as directory:
            client = EtsyDraftClient(_MemoryShop(), DraftLedger(Path(directory)))
            first = prepare_etsy_draft(evidence, client)
            second = prepare_etsy_draft(evidence, client)
    except DraftGateError as error:
        raise SyntheticPathRefusal(error.gate) from error
    if first != second or first.state != "draft" or not first.ready:
        raise SyntheticPathRefusal("etsy_draft")
    return first


def _preflight(copy: _ListingCopy, assets: tuple[BoundAsset, ...]):
    images = tuple(asset.storage_uri for asset in assets if asset.kind == "listing_image")
    videos = sum(1 for asset in assets if asset.kind == "walkthrough")
    result = run_etsy_preflight(
        EtsyPreflightDraft(
            quantity=999,
            tags=copy.tags,
            images=images,
            videos=videos,
            claims=(PreflightClaim(text=copy.description, fact_ref="fixture:buyer-problem"),),
        )
    )
    if isinstance(result, PreflightBlocked) or result.outcome is not BranchOutcome.PASS:
        raise SyntheticPathRefusal("preflight")
    return result


def _weekly() -> UUID:
    start = _WHEN - timedelta(days=7)
    rows = snapshots_from_fixture(
        (
            {
                "snapshot_id": _stable("weekly-snapshot"),
                "listing_id": _stable("listing"),
                "listing_version": 1,
                "provider": "fixture",
                "observed_at": _WHEN,
                "views": 20,
                "favourites": 3,
                "orders": 4,
                "gross_revenue": Decimal("35.96"),
                "currency": "USD",
                "reconciled": True,
                "window_start": start,
                "window_end": _WHEN,
                "evidence": _evidence("weekly"),
            },
        )
    )
    plan = plan_weekly(
        (ActiveListing(listing_id=_stable("listing"), listing_version=1, active=True),),
        window_start=start,
        window_end=_WHEN,
        prior_snapshots=tuple(item.snapshot for item in rows),
    )
    stored = persist_weekly_plan(
        TriggerLedger(),
        shop_id=_stable("shop"),
        plan=plan,
        next_fire_at=_WHEN + timedelta(days=7),
    )
    if not stored:
        raise SyntheticPathRefusal("weekly")
    return stored[0].shop_id


def _winner_listing(spec: ProductSpec) -> ListingCandidate:
    return ListingCandidate(
        listing_id=_stable("listing"),
        product_id=spec.product_id,
        spec_id=spec.spec_id,
        workflow_id=spec.workflow_id,
        shop_id=_stable("shop"),
        live_days=30,
        in_window=True,
        has_defect=False,
        snapshot=SnapshotView(
            snapshot_id=_stable("winner-snapshot"),
            views=20,
            favourites=3,
            orders=4,
            gross_revenue=3596,
            reconciled=True,
        ),
    )


def _cull_cohort() -> tuple[ListingCandidate, ...]:
    return (
        _candidate(1, views=0, orders=0, revenue=0, favourites=0),
        _candidate(2, views=0, orders=0, revenue=0, favourites=2),
        _candidate(3, views=0, orders=1, revenue=1, favourites=0),
        _candidate(4, views=0, orders=2, revenue=2, favourites=0),
        _candidate(5, views=0, orders=6, revenue=10, favourites=4),
    )


def _candidate(
    number: int,
    *,
    views: int,
    orders: int,
    revenue: int,
    favourites: int,
) -> ListingCandidate:
    return ListingCandidate(
        listing_id=_stable(f"cohort-{number}"),
        product_id=_stable(f"cohort-product-{number}"),
        spec_id=_stable(f"cohort-spec-{number}"),
        workflow_id=_stable(f"cohort-workflow-{number}"),
        shop_id=_stable("cohort-shop"),
        live_days=30,
        in_window=True,
        has_defect=False,
        snapshot=SnapshotView(
            snapshot_id=_stable(f"cohort-snapshot-{number}"),
            views=views,
            favourites=favourites,
            orders=orders,
            gross_revenue=revenue,
            reconciled=True,
        ),
    )


def _build_result(
    spec: ProductSpec,
    name: str,
    kind: Literal["PRIMARY", "VARIANT", "REPAIR", "ASSET", "DELIVERY"],
    checkpoints: tuple[str, ...],
) -> BuildResult:
    pages = "\n".join(f"{hub}: fixture page" for hub in spec.hubs)
    return BuildResult(
        result_id=_stable(name),
        workflow_id=spec.workflow_id,
        product_id=spec.product_id,
        spec_id=spec.spec_id,
        build_version=1,
        build_kind=kind,
        artifacts=(_artifact(name, body=pages),),
        checkpoint_names=checkpoints,
        completed_at=_WHEN,
    )


def _bound(
    spec: ProductSpec,
    kind: Literal["screenshot", "listing_image", "walkthrough", "delivery_pdf"],
    role: str,
    source: tuple[str, ...],
) -> BoundAsset:
    digest = _sha(f"{spec.product_id}:{role}")
    return BoundAsset(
        product_id=spec.product_id,
        spec_version=spec.version,
        build_version=1,
        source_screenshot_sha256=source,
        merchandising_version=_RULE_VERSION,
        template_version=_RULE_VERSION,
        output_sha256=digest,
        width_px=2000 if kind != "delivery_pdf" else None,
        height_px=2000 if kind != "delivery_pdf" else None,
        page_count=12 if kind == "delivery_pdf" else None,
        qa_status="passed",
        storage_uri=fixture_storage_uri(spec.product_id, spec.version, digest),
        kind=kind,
    )


def _artifact(
    name: str,
    *,
    body: str = "fixture",
    parent: tuple[UUID, ...] = (),
) -> ArtifactReference:
    payload = body.encode()
    return ArtifactReference(
        artifact_id=_stable(f"artifact-{name}"),
        logical_role=name,
        media_type="text/plain",
        sha256=hashlib.sha256(payload).hexdigest(),
        byte_size=len(payload),
        storage_reference=f"fixture://synthetic/{name}",
        producing_job_id=_stable(f"job-{name}"),
        producing_agent_run_id=_stable(f"run-{name}"),
        created_at=_WHEN,
        sensitivity="INTERNAL",
        retention_class="fixture",
        parent_artifact_ids=parent,
    )


def _evidence(name: str) -> EvidenceReference:
    return EvidenceReference(
        evidence_id=_stable(f"evidence-{name}"),
        evidence_type="synthetic-path",
        source_reference=f"fixture://synthetic/{name}",
        observed_at=_WHEN,
        sha256=_sha(name),
        safe_summary=name,
    )


def _receipt(path: str, step: str, artifact_id: UUID, outcome: str) -> PathReceipt:
    return PathReceipt(path=path, step=step, artifact_id=artifact_id, outcome=outcome)


def _require(path: str, receipts: Sequence[PathReceipt], steps: Sequence[str]) -> None:
    found = [item.step for item in receipts if item.path == path]
    if tuple(found) != tuple(steps):
        raise SyntheticPathRefusal(f"skipped:{path}")


def _stable(name: str) -> UUID:
    return uuid5(_NAMESPACE, name)


def _sha(name: str) -> str:
    return hashlib.sha256(name.encode()).hexdigest()
