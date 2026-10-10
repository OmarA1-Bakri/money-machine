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
    REQUIRED_FACT_KEYS,
    VIDEO_BEATS,
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
            if correction.rejection_class not in {
                "invented_page_count",
                "nonexistent_feature",
                "variant_not_built",
                "unsupported_automation",
                "invented_review",
                "invented_sales",
                "invented_trust_bar",
                "unsupported_social_proof",
                "unknown_fact",
                "tag_count",
                "section_count",
            }:
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
    currency = facts["currency"].fact_value

    hub_names = fact_items(facts["hubs"].fact_value)
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
        shop,
        support,
        gift,
        currency,
        request,
    )
    if tuple(section.role for section in sections) != DESCRIPTION_ROLES:
        raise MerchandisingInputError("generator did not emit the eight description roles")
    tags = _tags(request, facts)
    hero = _hero(identity, problem)
    strip = _image_strip(
        identity, problem, page, hub_claims, variant_claims, device_claims, access, hub_names
    )
    video = _video(dashboard, hub_claims, variant_claims, access, hub_names)
    price_sale = PriceSaleData(
        currency=currency,
        price=request.price,
        anchor_price=request.anchor_price,
        quantity=request.rules.quantity,
        sale_configured=request.anchor_price > request.price,
    )
    return ListingDraft(
        title=_title(identity, category),
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
    shop: ListingClaim,
    support: ListingClaim,
    gift: ListingClaim,
    currency: str,
    request: MerchandisingInput,
) -> tuple[DescriptionSection, ...]:
    hub_text = ", ".join(claim.stated_value for claim in hubs)
    feature_text = "; ".join(claim.stated_value for claim in features)
    variant_text = ", ".join(claim.stated_value for claim in variants)
    device_text = ", ".join(claim.stated_value for claim in devices)
    dashboard_text = _dashboard_sentence(dashboard, request)
    support_text = _support_sentence(support, gift, request)
    ordered: tuple[tuple[DescriptionRole, str, tuple[UUID, ...]], ...] = (
        (
            "hook",
            f"{identity.stated_value} {category.stated_value}. {problem.stated_value}",
            (identity.claim_id, category.claim_id, problem.claim_id),
        ),
        (
            "included",
            f"{page.stated_value} pages. Hubs: {hub_text}.",
            (page.claim_id, *(claim.claim_id for claim in hubs)),
        ),
        (
            "audience",
            f"Made for {identity.stated_value}. Shop {shop.stated_value}.",
            (identity.claim_id, shop.claim_id),
        ),
        (
            "how_it_works",
            f"Duplicate the template. Access link: {access.stated_value}.",
            (access.claim_id,),
        ),
        (
            "features",
            f"{feature_text}. {dashboard_text}",
            (dashboard.claim_id, *(claim.claim_id for claim in features)),
        ),
        (
            "variants",
            f"Variants: {variant_text}. Devices: {device_text}.",
            tuple(claim.claim_id for claim in (*variants, *devices)),
        ),
        (
            "support",
            support_text,
            (support.claim_id, gift.claim_id),
        ),
        (
            "offer",
            (
                f"Price {price.stated_value} {currency}. "
                f"Anchor {anchor.stated_value} {currency}. "
                f"Quantity {request.rules.quantity}. Digital delivery."
            ),
            (price.claim_id, anchor.claim_id),
        ),
    )
    return tuple(
        DescriptionSection(role=role, text=text, claim_ids=claim_ids)
        for role, text, claim_ids in ordered
    )


def _dashboard_sentence(dashboard: ListingClaim, request: MerchandisingInput) -> str:
    if not request.notification_dashboard.present:
        return "Notification dashboard is not in this build."
    outputs = ", ".join(fact_items(dashboard.stated_value))
    return f"Notification dashboard: {outputs}."


def _support_sentence(
    support: ListingClaim,
    gift: ListingClaim,
    request: MerchandisingInput,
) -> str:
    if request.support.offered:
        support_text = f"Support channel: {request.support.channel}."
    else:
        support_text = "Support is not offered."
    if request.free_gift.offered:
        gift_text = f"Free gift: {request.free_gift.name}."
        if request.free_gift.community is not None:
            gift_text = f"{gift_text} Free community: {request.free_gift.community}."
    else:
        gift_text = "No free gift is configured."
    return (
        f"{support_text} {gift_text} "
        f"Fact support {support.stated_value}. Fact gift {gift.stated_value}."
    )


def _title(identity: ListingClaim, category: ListingClaim) -> str:
    title = f"{identity.stated_value} {category.stated_value}"
    if len(title) <= 140:
        return title
    return title[:140].rstrip()


def _hero(identity: ListingClaim, problem: ListingClaim) -> str:
    return f"{identity.stated_value}. {problem.stated_value}"


def _image_strip(
    identity: ListingClaim,
    problem: ListingClaim,
    page: ListingClaim,
    hubs: tuple[ListingClaim, ...],
    variants: tuple[ListingClaim, ...],
    devices: tuple[ListingClaim, ...],
    access: ListingClaim,
    hub_names: tuple[str, ...],
) -> tuple[ImageStripLine, ...]:
    lines: dict[ImageRole, ImageStripLine] = {
        "hero": ImageStripLine(
            role="hero",
            text=f"{identity.stated_value}. {problem.stated_value}",
            claim_ids=(identity.claim_id, problem.claim_id),
        ),
        "overview": ImageStripLine(
            role="overview",
            text=f"{page.stated_value} pages in {identity.stated_value}.",
            claim_ids=(page.claim_id, identity.claim_id),
        ),
        "colour_options": ImageStripLine(
            role="colour_options",
            text="Variants: " + ", ".join(claim.stated_value for claim in variants) + ".",
            claim_ids=tuple(claim.claim_id for claim in variants),
        ),
        "devices": ImageStripLine(
            role="devices",
            text="Devices: " + ", ".join(claim.stated_value for claim in devices) + ".",
            claim_ids=tuple(claim.claim_id for claim in devices),
        ),
        "how_it_works": ImageStripLine(
            role="how_it_works",
            text=f"Duplicate the template. Access link: {access.stated_value}.",
            claim_ids=(access.claim_id,),
        ),
    }
    framed = zip(_HUB_FRAMES, hubs[:5], hub_names[:5], strict=True)
    for role, claim, name in framed:
        lines[role] = ImageStripLine(
            role=role,
            text=f"Hub: {name}.",
            claim_ids=(claim.claim_id,),
        )
    return tuple(lines[role] for role in IMAGE_ROLES)


def _video(
    dashboard: ListingClaim,
    hubs: tuple[ListingClaim, ...],
    variants: tuple[ListingClaim, ...],
    access: ListingClaim,
    hub_names: tuple[str, ...],
) -> tuple[VideoBeat, ...]:
    strongest = hubs[:3]
    names = ", ".join(hub_names[:3])
    beats: dict[VideoRole, VideoBeat] = {
        "dashboard": VideoBeat(
            role="dashboard",
            text=f"Dashboard output: {dashboard.stated_value}.",
            claim_ids=(dashboard.claim_id,),
        ),
        "notification_panel": VideoBeat(
            role="notification_panel",
            text=f"Notification panel: {dashboard.stated_value}.",
            claim_ids=(dashboard.claim_id,),
        ),
        "strongest_hubs": VideoBeat(
            role="strongest_hubs",
            text=f"Hubs: {names}.",
            claim_ids=tuple(claim.claim_id for claim in strongest),
        ),
        "colour_options": VideoBeat(
            role="colour_options",
            text="Variants: " + ", ".join(claim.stated_value for claim in variants) + ".",
            claim_ids=tuple(claim.claim_id for claim in variants),
        ),
        "duplication_access": VideoBeat(
            role="duplication_access",
            text=f"Duplicate the template. Access link: {access.stated_value}.",
            claim_ids=(access.claim_id,),
        ),
    }
    return tuple(beats[role] for role in VIDEO_BEATS)


def _tags(
    request: MerchandisingInput,
    facts: dict[str, ProductFact],
) -> tuple[str, ...]:
    sources: list[str] = [
        facts["identity"].fact_value,
        facts["base_category"].fact_value,
        facts["shop_name"].fact_value,
    ]
    sources.extend(fact_items(facts["hubs"].fact_value))
    sources.extend(fact_items(facts["features"].fact_value))
    sources.extend(fact_items(facts["colour_names"].fact_value))
    sources.extend(fact_items(facts["supported_devices"].fact_value))
    tags: list[str] = []
    seen: set[str] = set()
    for source in sources:
        tag = _etsy_tag(source)
        if tag == "" or tag in seen:
            continue
        seen.add(tag)
        tags.append(tag)
        if len(tags) == request.rules.tags:
            return tuple(tags)
    raise MerchandisingInputError(
        f"facts do not yield {request.rules.tags} grounded tags, got {len(tags)}"
    )


def _etsy_tag(value: str) -> str:
    words: list[str] = []
    for raw in value.casefold().split():
        cleaned = "".join(character for character in raw if character.isalnum())
        if cleaned:
            words.append(cleaned)
    tag = ""
    for word in words:
        candidate = word if tag == "" else f"{tag} {word}"
        if len(candidate) > 20:
            break
        tag = candidate
    return tag


def _require_equal(fact: ProductFact, expected: str, label: str) -> None:
    if fact.fact_value != expected:
        raise MerchandisingInputError(f"{label} fact does not match the built input")


def validation_outcome(copy: ListingDraft, request: MerchandisingInput) -> ClaimValidation:
    """Public alias so callers can inspect a draft without generating another."""
    return validate_claims(copy, request)
