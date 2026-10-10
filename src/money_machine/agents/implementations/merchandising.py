"""A10 merchandising copy, fixture-only.

The agent stays DESIGNED and is not registered for production execution.
Copy is derived from ProductFacts. This module does not call LLMProvider,
Notion, or Etsy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid5

from money_machine.agents.contracts.merchandising import (
    DESCRIPTION_ROLES,
    IMAGE_ROLES,
    REJECTION_CLASSES,
    REQUIRED_FACT_KEYS,
    VIDEO_BEATS,
    CitedText,
    ClaimCorrection,
    ClaimKind,
    DescriptionRole,
    DescriptionSection,
    ImageRole,
    ImageStripLine,
    ListingClaim,
    ListingCopy,
    ListingDraft,
    MerchandisingInput,
    PriceSaleData,
    ProductFact,
    VideoBeat,
    VideoRole,
    encode_dashboard,
    encode_free_gift,
    encode_support,
    fact_items,
    money_text,
)
from money_machine.config.loader import load_yaml_model
from money_machine.config.settings import ProductRulesConfig
from money_machine.domain.models.rules import ListingRules
from money_machine.domain.services.claim_validation import ClaimValidation, validate_claims
from money_machine.domain.services.listing_text import TextSlot, render

MAX_CLAIM_ATTEMPTS = 3
"""Initial draft plus two regenerations. The third failure is closed."""

_NAMESPACE = UUID("a1000000-0000-4000-8000-000000000010")
_HUB_FRAMES: tuple[ImageRole, ...] = ("hub_1", "hub_2", "hub_3", "hub_4", "hub_5")


class MerchandisingInputError(ValueError):
    """The supplied facts and the built product do not agree."""


class ClaimValidationClosed(Exception):
    """Validation still failed after the bounded correction attempts."""

    def __init__(self, corrections: tuple[ClaimCorrection, ...], attempts: int) -> None:
        self.corrections = corrections
        self.attempts = attempts
        super().__init__(f"claim validation failed closed after {attempts} attempts")


class CopyGenerator(Protocol):
    """Fixture seam. The default generator does not call a network provider."""

    def generate(
        self,
        request: MerchandisingInput,
        corrections: tuple[ClaimCorrection, ...],
    ) -> ListingDraft:
        """Return one draft. Corrections are the previous rejection, if any."""
        ...


class DeterministicCopyGenerator:
    """Rebuild listing copy from facts. Rejected statements are not copied."""

    def generate(
        self,
        request: MerchandisingInput,
        corrections: tuple[ClaimCorrection, ...],
    ) -> ListingDraft:
        require_consistent(request)
        for correction in corrections:
            if correction.rejection_class not in REJECTION_CLASSES:
                raise MerchandisingInputError("unknown correction class")
        return _draft_from_facts(request)


def merchandise(
    request: MerchandisingInput,
    generator: CopyGenerator | None = None,
    *,
    max_attempts: int = MAX_CLAIM_ATTEMPTS,
) -> ListingCopy:
    """Generate copy and regenerate from corrections until it validates."""
    if max_attempts < 1:
        raise MerchandisingInputError("max_attempts must be at least 1")
    require_consistent(request)
    active = generator if generator is not None else DeterministicCopyGenerator()
    corrections: tuple[ClaimCorrection, ...] = ()
    draft = active.generate(request, corrections)
    for attempt in range(max_attempts):
        outcome = validate_claims(draft, request)
        if outcome.passed:
            return ListingCopy(draft=draft, rules=request.rules)
        corrections = outcome.corrections
        if attempt + 1 == max_attempts:
            break
        draft = active.generate(request, corrections)
    raise ClaimValidationClosed(corrections, max_attempts)


def require_consistent(request: MerchandisingInput) -> None:
    """Fail closed when a fact disagrees with the built product or the spec."""
    if request.rules != configured_listing_rules():
        raise MerchandisingInputError("listing rules must be the configured playbook rules")
    facts = {fact.fact_key: fact for fact in request.facts}
    missing = [key for key in REQUIRED_FACT_KEYS if key not in facts]
    if missing:
        raise MerchandisingInputError("missing product facts: " + ", ".join(missing))
    _require_equal(facts["page_count"], str(request.page_count), "page_count")
    hubs = fact_items(facts["hubs"].fact_value)
    if hubs != request.hubs:
        raise MerchandisingInputError("hubs fact does not match the built hub list")
    if len(hubs) < len(_HUB_FRAMES):
        raise MerchandisingInputError("image strip needs five built hubs")
    colours = fact_items(facts["colour_names"].fact_value)
    built = tuple(variant.name for variant in request.variants)
    if colours != built:
        raise MerchandisingInputError("colour_names fact does not match the built variants")
    _require_equal(facts["identity"], request.spec.identity, "identity")
    _require_equal(facts["base_category"], request.spec.base_category, "base_category")
    _require_equal(facts["buyer_problem"], request.spec.buyer_problem, "buyer_problem")
    _require_equal(facts["price"], money_text(request.price), "price")
    if money_text(request.spec.real_price) != money_text(request.price):
        raise MerchandisingInputError("price does not match the product spec")
    _require_equal(facts["anchor_price"], money_text(request.anchor_price), "anchor_price")
    if money_text(request.spec.anchor_price) != money_text(request.anchor_price):
        raise MerchandisingInputError("anchor_price does not match the product spec")
    _require_equal(facts["currency"], request.spec.currency, "currency")
    _require_equal(facts["shop_name"], request.shop_name, "shop_name")
    _require_equal(facts["support"], encode_support(request.support), "support")
    _require_equal(facts["free_gift"], encode_free_gift(request.free_gift), "free_gift")
    _require_equal(
        facts["dashboard_outputs"],
        encode_dashboard(request.notification_dashboard),
        "dashboard_outputs",
    )
    if any(item == "" for item in fact_items(facts["features"].fact_value)):
        raise MerchandisingInputError("features fact contains an empty item")
    if not fact_items(facts["features"].fact_value):
        raise MerchandisingInputError("features fact is empty")
    if not fact_items(facts["supported_devices"].fact_value):
        raise MerchandisingInputError("supported_devices fact is empty")
    if any(item == "" for item in fact_items(facts["supported_devices"].fact_value)):
        raise MerchandisingInputError("supported_devices fact contains an empty item")


def configured_listing_rules() -> ListingRules:
    """Playbook listing shape from ``config/product_rules.yaml``."""
    root = Path(__file__).resolve().parents[4]
    config = load_yaml_model(root / "config" / "product_rules.yaml", ProductRulesConfig)
    return config.listing_rules()


def _draft_from_facts(request: MerchandisingInput) -> ListingDraft:
    facts = {fact.fact_key: fact for fact in request.facts}
    claims: dict[UUID, ListingClaim] = {}

    def add(kind: ClaimKind, key: str, stated: str) -> ListingClaim:
        fact = facts[key]
        claim = ListingClaim(
            claim_id=uuid5(_NAMESPACE, f"{kind}:{fact.fact_id}:{stated}"),
            kind=kind,
            fact_id=fact.fact_id,
            stated_value=stated,
        )
        claims[claim.claim_id] = claim
        return claim

    identity = add("identity", "identity", facts["identity"].fact_value)
    category = add("category", "base_category", facts["base_category"].fact_value)
    problem = add("buyer_problem", "buyer_problem", facts["buyer_problem"].fact_value)
    page = add("page_count", "page_count", facts["page_count"].fact_value)
    hub_claims = tuple(add("hub", "hubs", name) for name in fact_items(facts["hubs"].fact_value))
    feature_claims = tuple(
        add("feature", "features", name) for name in fact_items(facts["features"].fact_value)
    )
    variant_claims = tuple(
        add("variant", "colour_names", name)
        for name in fact_items(facts["colour_names"].fact_value)
    )
    device_claims = tuple(
        add("device", "supported_devices", name)
        for name in fact_items(facts["supported_devices"].fact_value)
    )
    dashboard = add("dashboard", "dashboard_outputs", facts["dashboard_outputs"].fact_value)
    access = add("access", "secret_links", facts["secret_links"].fact_value)
    price = add("price", "price", facts["price"].fact_value)
    anchor = add("anchor", "anchor_price", facts["anchor_price"].fact_value)
    shop = add("shop", "shop_name", facts["shop_name"].fact_value)
    support = add("support", "support", facts["support"].fact_value)
    gift = add("free_gift", "free_gift", facts["free_gift"].fact_value)
    currency_claim = add("currency", "currency", facts["currency"].fact_value)
    currency = currency_claim.stated_value

    sections = _sections(
        identity,
        category,
        problem,
        page,
        hub_claims,
        feature_claims,
        variant_claims,
        device_claims,
        dashboard,
        access,
        price,
        anchor,
        currency_claim,
        shop,
        support,
        gift,
        request.rules.quantity,
    )
    if tuple(section.role for section in sections) != DESCRIPTION_ROLES:
        raise MerchandisingInputError("generator did not emit the eight description roles")
    tag_sources = (
        identity,
        category,
        shop,
        *hub_claims,
        *feature_claims,
        *variant_claims,
        *device_claims,
    )
    tags = _tags(request, tag_sources)
    hero = _cite("hero", (identity, problem), request.rules.quantity)
    strip = _image_strip(
        identity, problem, page, hub_claims, variant_claims, device_claims, access, request
    )
    video = _video(dashboard, hub_claims, variant_claims, access, request)
    price_sale = PriceSaleData(
        currency=currency,
        price=request.price,
        anchor_price=request.anchor_price,
        quantity=request.rules.quantity,
        sale_configured=request.anchor_price > request.price,
    )
    return ListingDraft(
        title=_cite("title", (identity, category), request.rules.quantity),
        description_sections=sections,
        tags=tags,
        hero_copy=hero,
        image_strip=strip,
        video_sequence=video,
        price_sale=price_sale,
        claims=tuple(claims.values()),
    )


def _sections(
    identity: ListingClaim,
    category: ListingClaim,
    problem: ListingClaim,
    page: ListingClaim,
    hubs: tuple[ListingClaim, ...],
    features: tuple[ListingClaim, ...],
    variants: tuple[ListingClaim, ...],
    devices: tuple[ListingClaim, ...],
    dashboard: ListingClaim,
    access: ListingClaim,
    price: ListingClaim,
    anchor: ListingClaim,
    currency: ListingClaim,
    shop: ListingClaim,
    support: ListingClaim,
    gift: ListingClaim,
    quantity: int,
) -> tuple[DescriptionSection, ...]:
    ordered: tuple[tuple[DescriptionRole, str, tuple[ListingClaim, ...]], ...] = (
        ("hook", "hook", (identity, category, problem)),
        ("included", "included", (page, *hubs)),
        ("audience", "audience", (identity, shop)),
        ("how_it_works", "access_line", (access,)),
        ("features", "features", (*features, dashboard)),
        ("variants", "variant_devices", (*variants, *devices)),
        ("support", "support", (support, gift)),
        ("offer", "offer", (price, currency, anchor)),
    )
    return tuple(
        _section(role, template_id, claims, quantity) for role, template_id, claims in ordered
    )


def _section(
    role: DescriptionRole,
    template_id: str,
    claims: tuple[ListingClaim, ...],
    quantity: int,
) -> DescriptionSection:
    text, claim_ids = _rendered(template_id, claims, quantity)
    return DescriptionSection(
        role=role,
        template_id=template_id,
        text=text,
        claim_ids=claim_ids,
    )


def _image_strip(
    identity: ListingClaim,
    problem: ListingClaim,
    page: ListingClaim,
    hubs: tuple[ListingClaim, ...],
    variants: tuple[ListingClaim, ...],
    devices: tuple[ListingClaim, ...],
    access: ListingClaim,
    request: MerchandisingInput,
) -> tuple[ImageStripLine, ...]:
    quantity = request.rules.quantity
    lines: dict[ImageRole, ImageStripLine] = {
        "hero": _image("hero", "hero", (identity, problem), quantity),
        "overview": _image("overview", "overview", (page, identity), quantity),
        "colour_options": _image("colour_options", "variant_line", variants, quantity),
        "devices": _image("devices", "device_line", devices, quantity),
        "how_it_works": _image("how_it_works", "access_line", (access,), quantity),
    }
    for role, claim in zip(_HUB_FRAMES, hubs[:5], strict=True):
        lines[role] = _image(role, "hub_frame", (claim,), quantity)
    return tuple(lines[role] for role in IMAGE_ROLES)


def _image(
    role: ImageRole,
    template_id: str,
    claims: tuple[ListingClaim, ...],
    quantity: int,
) -> ImageStripLine:
    text, claim_ids = _rendered(template_id, claims, quantity)
    return ImageStripLine(role=role, template_id=template_id, text=text, claim_ids=claim_ids)


def _video(
    dashboard: ListingClaim,
    hubs: tuple[ListingClaim, ...],
    variants: tuple[ListingClaim, ...],
    access: ListingClaim,
    request: MerchandisingInput,
) -> tuple[VideoBeat, ...]:
    quantity = request.rules.quantity
    beats: dict[VideoRole, VideoBeat] = {
        "dashboard": _beat("dashboard", "video_dashboard", (dashboard,), quantity),
        "notification_panel": _beat(
            "notification_panel",
            "video_notification",
            (dashboard,),
            quantity,
        ),
        "strongest_hubs": _beat("strongest_hubs", "video_hubs", hubs[:3], quantity),
        "colour_options": _beat("colour_options", "variant_line", variants, quantity),
        "duplication_access": _beat("duplication_access", "access_line", (access,), quantity),
    }
    return tuple(beats[role] for role in VIDEO_BEATS)


def _beat(
    role: VideoRole,
    template_id: str,
    claims: tuple[ListingClaim, ...],
    quantity: int,
) -> VideoBeat:
    text, claim_ids = _rendered(template_id, claims, quantity)
    return VideoBeat(role=role, template_id=template_id, text=text, claim_ids=claim_ids)


def _cite(template_id: str, claims: tuple[ListingClaim, ...], quantity: int) -> CitedText:
    text, claim_ids = _rendered(template_id, claims, quantity)
    return CitedText(template_id=template_id, text=text, claim_ids=claim_ids)


def _tags(request: MerchandisingInput, sources: tuple[ListingClaim, ...]) -> tuple[CitedText, ...]:
    tags: list[CitedText] = []
    seen: set[str] = set()
    for claim in sources:
        text, claim_ids = _rendered("tag", (claim,), request.rules.quantity)
        if text == "" or text in seen:
            continue
        seen.add(text)
        tags.append(CitedText(template_id="tag", text=text, claim_ids=claim_ids))
        if len(tags) == request.rules.tags:
            return tuple(tags)
    raise MerchandisingInputError(
        f"facts do not yield {request.rules.tags} grounded tags, got {len(tags)}"
    )


def _rendered(
    template_id: str,
    claims: tuple[ListingClaim, ...],
    quantity: int,
) -> tuple[str, tuple[UUID, ...]]:
    slots = tuple(TextSlot(claim.kind, claim.stated_value) for claim in claims)
    return render(template_id, slots, quantity=quantity), tuple(claim.claim_id for claim in claims)


def _require_equal(fact: ProductFact, expected: str, label: str) -> None:
    if fact.fact_value != expected:
        raise MerchandisingInputError(f"{label} fact does not match the built input")


def validation_outcome(copy: ListingDraft, request: MerchandisingInput) -> ClaimValidation:
    """Public alias so callers can inspect a draft without generating another."""
    return validate_claims(copy, request)
