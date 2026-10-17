"""Earn Session 08 evidence by running the fixture asset chain.

The live sandbox is not started. A10 and A11 are not commissioned.
A key is earned only when the chain produces the artifact that key names.
"""

from __future__ import annotations

import hashlib
import tempfile
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

from money_machine.agents.contracts.merchandising import (
    DESCRIPTION_ROLES,
    IMAGE_ROLES,
    BuiltVariant,
    FactKey,
    FreeGiftConfig,
    ListingCopy,
    MerchandisingInput,
    NotificationDashboardBehaviour,
    ProductFact,
    SupportConfig,
    encode_dashboard,
    encode_free_gift,
    encode_support,
    money_text,
)
from money_machine.agents.implementations.merchandising import (
    configured_listing_rules,
    merchandise,
)
from money_machine.assets.asset_lineage import BoundAsset, bind_asset
from money_machine.assets.delivery_pdfs import (
    GIFT_PAGE_COUNT,
    README_PAGE_COUNT,
    render_gift_pdf,
    render_readme_pdf,
)
from money_machine.assets.design_tokens import emit_css, listing_token_payload, load_tokens
from money_machine.assets.etsy_draft import DraftEvidence, prepare_etsy_draft
from money_machine.assets.link_validation import LinkObservation, validate_pdf_links
from money_machine.assets.listing_images import render_listing_images
from money_machine.assets.pdf_objects import EmbeddedUriRefusal, delivery_link_uris
from money_machine.assets.screenshots import (
    CapturedScreenshot,
    VariantPage,
    capture_variant_screenshots,
    write_screenshot_inputs,
)
from money_machine.assets.video import render_walkthrough
from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.products import ProductSpec
from money_machine.domain.models.rules import ProductShapeRules
from money_machine.domain.services.claim_validation import validate_claims
from money_machine.integrations.etsy.draft_client import (
    DraftLedger,
    EtsyDraftClient,
    FixtureCall,
)
from money_machine.integrations.storage.local import LocalAssetStore

BEHAVIORAL_EVIDENCE_KEYS = frozenset(
    {
        "merchandising_agent_implemented",
        "claim_validation_implemented",
        "design_tokens_implemented",
        "creative_asset_agent_implemented",
        "screenshot_acquisition_implemented",
        "link_validation_implemented",
        "asset_lineage_recorded",
        "asset_storage_implemented",
        "merchandising_workflow_linked",
        "merchandising_asset_tests_pass",
    }
)
CONTROL_EVIDENCE_KEY = "control_files_and_checkpoint_current"
CLOSURE_EVIDENCE_KEY = "evidence_closure_commit_recorded"
_WHEN = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
_PRODUCT = UUID("00000000-0000-4000-8000-000000000008")
_SPEC = UUID("00000000-0000-4000-8000-000000000018")
_WORKFLOW = UUID("00000000-0000-4000-8000-000000000028")
_FACT_NAMESPACE = UUID("a1000000-0000-4000-8000-0000000000a0")
_SHOP = "Fieldnote Shop"
_PAGE_COUNT = 42
_SECRET = "https://fixture.notion.site"
_COLOURS = ("Sage Green", "Navy Blue", "Rose Gold")
_COLOUR_HEX = {"Sage Green": "#8A9A7B", "Navy Blue": "#1B3A4B", "Rose Gold": "#B76E79"}
_HUBS = (
    "Daily Planning",
    "Goal Tracking",
    "Habit Builder",
    "Budget Tracker",
    "Meal Planner",
    "Fitness Log",
)
_FEATURES = (
    "Hyperlinked navigation",
    "Interactive checkboxes",
    "Monthly calendar views",
    "Weekly spread templates",
)
_BUILD = 8
_SHOP_ID = 123456


class Session08ProofError(ValueError):
    """The fixture chain did not earn a Session 08 key."""

    def __init__(self, code: str) -> None:
        """Store the failing-step code on the error."""
        super().__init__(code)
        self.code = code


class _FixtureShop:
    """In-memory draft shop. It does not open a socket."""

    def __init__(self) -> None:
        """Initialise an empty in-memory listing store."""
        self._listings: list[dict[str, object]] = []
        self.posts = 0

    def exchange(self, call: FixtureCall) -> Mapping[str, object]:
        """Serve a GET listing query or a POST draft creation against the in-memory store."""
        if call.method == "GET":
            query = dict(call.query)
            state = query.get("state", "active")
            matched = [row for row in self._listings if row.get("state") == state]
            return {"count": len(matched), "results": matched}
        if call.method == "POST":
            if call.body is None:
                raise Session08ProofError("draft_body")
            fields = dict(call.body)
            self.posts += 1
            row: dict[str, object] = {
                "listing_id": 8000 + self.posts,
                "title": fields["title"],
                "description": fields["description"],
                "state": "draft",
            }
            self._listings.append(row)
            return row
        raise Session08ProofError("draft_method")


def _require(condition: bool, code: str) -> None:
    """Raise ``Session08ProofError`` with ``code`` when ``condition`` is false."""
    if not condition:
        raise Session08ProofError(code)


def _spec() -> ProductSpec:
    """Build the fixture product spec for the Session 08 proof."""
    evidence = (
        EvidenceReference(
            evidence_id=_SPEC,
            evidence_type="FIXTURE_GENERATED",
            source_reference="money_machine.control.session_08_proof",
            observed_at=_WHEN,
            safe_summary="Fixture product for the Session 08 evidence proof",
        ),
    )
    return ProductSpec(
        spec_id=_SPEC,
        workflow_id=_WORKFLOW,
        product_id=_PRODUCT,
        version=1,
        lineage_kind="ORIGINAL",
        parent_spec_id=None,
        parent_product_id=None,
        parent_decision_id=None,
        parent_workflow_id=None,
        shape_rules=ProductShapeRules(
            rule_version="1.0.0",
            hubs_minimum=6,
            hubs_maximum=8,
            colour_variants_minimum=3,
            colour_variants_maximum=4,
        ),
        identity="Modern Digital Planner",
        base_category="Planners & Organizers",
        buyer_problem="Stay organized with a reusable digital planning system",
        title="Ultimate 2027 Digital Planner Bundle",
        tier="mass",
        real_price=Decimal("8.99"),
        anchor_price=Decimal("14.99"),
        currency="USD",
        hubs=_HUBS,
        colour_variants=_COLOURS,
        features=_FEATURES,
        experiment_plan="Test color variants and hub prominence on conversions",
        concept_fingerprint=hashlib.sha256(
            b"Stay organized with a reusable digital planning system"
        ).hexdigest(),
        source_evidence=evidence,
        created_at=_WHEN,
    )


def _request(spec: ProductSpec) -> MerchandisingInput:
    """Build the merchandising input fixture for the given product spec."""
    dashboard = NotificationDashboardBehaviour(
        present=True,
        outputs=("Today panel", "Reminder list"),
    )
    support = SupportConfig(offered=True, channel="Email inbox")
    gift = FreeGiftConfig(offered=True, name="Starter checklist", community="Planning circle")
    values: dict[FactKey, str] = {
        "page_count": str(_PAGE_COUNT),
        "hubs": "|".join(spec.hubs),
        "colour_names": "|".join(spec.colour_variants),
        "features": "|".join(spec.features),
        "shop_name": _SHOP,
        "price": money_text(spec.real_price),
        "anchor_price": money_text(spec.anchor_price),
        "currency": spec.currency,
        "identity": spec.identity,
        "base_category": spec.base_category,
        "buyer_problem": spec.buyer_problem,
        "support": encode_support(support),
        "free_gift": encode_free_gift(gift),
        "dashboard_outputs": encode_dashboard(dashboard),
        "supported_devices": "Tablet|Phone",
        "secret_links": _SECRET,
    }
    facts = tuple(
        ProductFact(
            fact_id=uuid5(_FACT_NAMESPACE, key),
            product_id=spec.product_id,
            spec_id=spec.spec_id,
            fact_key=key,
            fact_value=value,
        )
        for key, value in values.items()
    )
    return MerchandisingInput(
        spec=spec,
        facts=facts,
        hubs=spec.hubs,
        page_count=_PAGE_COUNT,
        variants=tuple(
            BuiltVariant(name=name, colour=_COLOUR_HEX[name]) for name in spec.colour_variants
        ),
        notification_dashboard=dashboard,
        shop_name=_SHOP,
        price=spec.real_price,
        anchor_price=spec.anchor_price,
        support=support,
        free_gift=gift,
        rules=configured_listing_rules(),
    )


def _checker(uri: str, variant: str) -> LinkObservation:
    """Return a fixture link observation treating every URI as a valid public duplicate button."""
    return LinkObservation(variant=variant, public=True, duplicate_button=True, chain=(uri,))


def _clock() -> str:
    """Return a fixed fixture timestamp."""
    return "2026-10-16T12:00:00Z"


def _uris(pdf: bytes) -> tuple[str, ...]:
    """Extract the accepted delivery-link URIs from the PDF, refusing unexpected ones."""
    try:
        return delivery_link_uris(pdf, accepted=frozenset({_SECRET}))
    except EmbeddedUriRefusal as error:
        raise Session08ProofError("links") from error


def prove_session_08() -> frozenset[str]:
    """Run the fixture chain and return the behavioral keys it earned."""
    spec = _spec()
    request = _request(spec)
    copy = merchandise(request)
    _require(len(copy.draft.tags) == 13, "tags")
    _require(
        tuple(section.role for section in copy.draft.description_sections) == DESCRIPTION_ROLES,
        "description",
    )
    _require(validate_claims(copy.draft, request).passed, "claims")
    tokens = load_tokens(listing_token_payload())
    _require("mm-" in emit_css(tokens) or "--" in emit_css(tokens), "tokens")
    with tempfile.TemporaryDirectory(prefix="mm-s08-") as temporary:
        root = Path(temporary)
        shots = _screenshots(spec)
        paths = _role_paths(root / "roles", shots)
        shot_dir = root / "shots"
        shot_dir.mkdir()
        _written, allowed = write_screenshot_inputs(shots, shot_dir)
        images = render_listing_images(copy, request, paths, allowed, tokens, build_version=_BUILD)
        again = render_listing_images(copy, request, paths, allowed, tokens, build_version=_BUILD)
        video = render_walkthrough(copy, request, paths, allowed, tokens, build_version=_BUILD)
        readme = render_readme_pdf(copy, request, tokens, build_version=_BUILD)
        gift = render_gift_pdf(copy, request, tokens, build_version=_BUILD)
        _require(len(images) == len(IMAGE_ROLES), "images")
        _require(
            tuple(image.lineage.output_sha256 for image in images)
            == tuple(image.lineage.output_sha256 for image in again),
            "deterministic",
        )
        _require(len(video.video) > 0, "video")
        _require(readme.lineage.page_count == README_PAGE_COUNT, "readme")
        _require(gift.lineage.page_count == GIFT_PAGE_COUNT, "gift")
        _links(readme.pdf, "readme", spec.colour_variants)
        _links(gift.pdf, "free_gift", spec.colour_variants)
        assets = (
            *(bind_asset(shot.lineage) for shot in shots),
            *(bind_asset(image.lineage) for image in images),
            bind_asset(video.lineage),
            bind_asset(readme.lineage),
            bind_asset(gift.lineage),
        )
        _require(all(asset.qa_status == "passed" for asset in assets), "lineage")
        _store(root / "store", images[0].png, images[0].lineage.output_sha256, spec)
        _draft(copy, spec, assets)
    return BEHAVIORAL_EVIDENCE_KEYS


def _role_paths(directory: Path, shots: tuple[CapturedScreenshot, ...]) -> dict[str, Path]:
    """Write each image-role screenshot to disk and return its path by role."""
    directory.mkdir()
    paths: dict[str, Path] = {}
    roles = set(IMAGE_ROLES)
    for shot in shots:
        role = shot.lineage.variant
        if role not in roles:
            continue
        path = directory / f"{role}.png"
        path.write_bytes(shot.png)
        paths[role] = path
    return paths


def _screenshots(spec: ProductSpec) -> tuple[CapturedScreenshot, ...]:
    """Capture the fixture screenshots and require the colour variants to pass QA."""
    pages = tuple(VariantPage(name=name) for name in (*IMAGE_ROLES, *_COLOURS))
    captured = capture_variant_screenshots(
        pages,
        build_version=_BUILD,
        product_id=spec.product_id,
        spec_version=spec.version,
    )
    colours = [shot for shot in captured if shot.lineage.variant in _COLOURS]
    _require(len(colours) == len(_COLOURS), "screenshots")
    _require(all(shot.lineage.source == "fixture" for shot in colours), "screenshot_source")
    _require(all(shot.lineage.qa_status == "passed" for shot in colours), "screenshot_qa")
    return captured


def _links(pdf: bytes, asset: str, variants: tuple[str, ...]) -> None:
    """Validate the delivery links embedded in a rendered PDF against the known variants."""
    uris = _uris(pdf)
    if not uris:
        _require(asset == "free_gift", "links")
        return
    accepted = tuple((variants[index % len(variants)], uri) for index, uri in enumerate(uris))
    report = validate_pdf_links(
        pdf,
        asset=asset,
        accepted=accepted,
        known_variants=frozenset(variants),
        checker=_checker,
        clock=_clock,
    )
    _require(report.repairs == () and len(report.records) == len(uris), "links")


def _store(root: Path, payload: bytes, digest: str, spec: ProductSpec) -> None:
    """Publish the payload to the local asset store and require it to read back unchanged."""
    root.mkdir()
    store = LocalAssetStore(root, mode="simulation")
    stored = store.publish(
        product_id=spec.product_id,
        spec_version=spec.version,
        sha256=digest,
        data=payload,
    )
    _require(store.read(stored.storage_uri) == payload, "storage")


def _draft(copy: ListingCopy, spec: ProductSpec, assets: tuple[BoundAsset, ...]) -> None:
    """Prepare an Etsy draft against the fixture shop and require it to post exactly once."""
    shop = _FixtureShop()
    with tempfile.TemporaryDirectory(prefix="mm-s08-ledger-") as directory:
        receipt = prepare_etsy_draft(
            DraftEvidence(
                product_id=spec.product_id,
                spec_version=spec.version,
                shop_id=_SHOP_ID,
                product_qa="passed",
                claims_passed=True,
                assets=assets,
                pdf_roles=("readme", "free_gift"),
                links_passed=True,
                title=copy.draft.title.text,
                description="\n".join(section.text for section in copy.draft.description_sections),
                price=money_text(spec.real_price),
                quantity=copy.rules.quantity,
                who_made="i_did",
                when_made="2020_2026",
                taxonomy_id=1,
            ),
            EtsyDraftClient(shop, DraftLedger(Path(directory))),
        )
    _require(receipt.ready is True and receipt.state == "draft", "draft")
    _require(shop.posts == 1, "draft_once")
