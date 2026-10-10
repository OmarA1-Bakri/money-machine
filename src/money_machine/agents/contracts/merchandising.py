"""A10 listing-copy contracts.

Wave 1 returns copy and fact-bound claims. It does not build ``ListingPackage``
and it does not write ``product_facts``. The playbook PDF is not in this tree.
The eight description roles, ten image-strip frames, and five video beats are
the listing structure named by the workbook listing package and Session 08.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from money_machine.domain.models._base import (
    ContractModel,
    CurrencyCode,
    NonEmptyStr,
    PositiveDecimal,
    PositiveInt,
)
from money_machine.domain.models.products import ProductSpec
from money_machine.domain.models.rules import ListingRules
from money_machine.domain.services.listing_text import normalize_tag

FactKey = Literal[
    "page_count",
    "hubs",
    "databases",
    "variants",
    "colour_names",
    "dashboard_outputs",
    "supported_devices",
    "secret_links",
    "free_update_policy",
    "build_version",
    "features",
    "shop_name",
    "price",
    "anchor_price",
    "currency",
    "support",
    "free_gift",
    "identity",
    "base_category",
    "buyer_problem",
    "automation",
    "reviews",
    "sales_count",
    "trust_bar",
    "social_proof",
]

ClaimKind = Literal[
    "page_count",
    "feature",
    "variant",
    "automation",
    "review",
    "sales_performance",
    "trust_bar",
    "social_proof",
    "hub",
    "dashboard",
    "device",
    "price",
    "anchor",
    "currency",
    "support",
    "free_gift",
    "shop",
    "identity",
    "category",
    "buyer_problem",
    "database",
    "access",
]

RejectionClass = Literal[
    "invented_page_count",
    "nonexistent_feature",
    "variant_not_built",
    "unsupported_automation",
    "invented_review",
    "invented_sales",
    "invented_trust_bar",
    "unsupported_social_proof",
    "unknown_fact",
    "unbound_text",
    "tag_count",
    "section_count",
]

DescriptionRole = Literal[
    "hook",
    "included",
    "audience",
    "how_it_works",
    "features",
    "variants",
    "support",
    "offer",
]

ImageRole = Literal[
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
]

VideoRole = Literal[
    "dashboard",
    "notification_panel",
    "strongest_hubs",
    "colour_options",
    "duplication_access",
]

DESCRIPTION_ROLES: Final[tuple[DescriptionRole, ...]] = (
    "hook",
    "included",
    "audience",
    "how_it_works",
    "features",
    "variants",
    "support",
    "offer",
)
IMAGE_ROLES: Final[tuple[ImageRole, ...]] = (
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
VIDEO_BEATS: Final[tuple[VideoRole, ...]] = (
    "dashboard",
    "notification_panel",
    "strongest_hubs",
    "colour_options",
    "duplication_access",
)
REJECTION_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "invented_page_count",
        "nonexistent_feature",
        "variant_not_built",
        "unsupported_automation",
        "invented_review",
        "invented_sales",
        "invented_trust_bar",
        "unsupported_social_proof",
        "unknown_fact",
        "unbound_text",
        "tag_count",
        "section_count",
    }
)
REQUIRED_FACT_KEYS: Final[tuple[FactKey, ...]] = (
    "page_count",
    "hubs",
    "colour_names",
    "features",
    "shop_name",
    "price",
    "anchor_price",
    "currency",
    "identity",
    "base_category",
    "buyer_problem",
    "support",
    "free_gift",
    "dashboard_outputs",
    "supported_devices",
    "secret_links",
)
ETSY_TAG_MAX: Final = 20


class ProductFact(ContractModel):
    """One verified fact a listing claim may cite. Not a database write."""

    fact_id: UUID
    product_id: UUID
    spec_id: UUID
    fact_key: FactKey
    fact_value: NonEmptyStr


class ListingClaim(ContractModel):
    """One statement in the listing copy, bound to one ProductFact."""

    claim_id: UUID
    kind: ClaimKind
    fact_id: UUID
    stated_value: NonEmptyStr


class ClaimCorrection(ContractModel):
    """The exact fix A10 must apply to one rejected claim."""

    claim_id: UUID
    rejection_class: RejectionClass
    fact_id: UUID | None = None
    correction: NonEmptyStr


class SupportConfig(ContractModel):
    """Support channel that may be claimed only when a fact matches it."""

    offered: bool
    channel: NonEmptyStr | None = None

    @model_validator(mode="after")
    def channel_matches_offer(self) -> Self:
        if self.offered and self.channel is None:
            raise ValueError("offered support names a channel")
        if not self.offered and self.channel is not None:
            raise ValueError("support that is not offered has no channel")
        if self.channel is not None and "|" in self.channel:
            raise ValueError("support channel cannot contain a pipe")
        return self


class FreeGiftConfig(ContractModel):
    """Optional free gift. Paid checkout links are not part of the gift."""

    offered: bool
    name: NonEmptyStr | None = None
    community: NonEmptyStr | None = None

    @model_validator(mode="after")
    def name_matches_offer(self) -> Self:
        if self.offered and self.name is None:
            raise ValueError("an offered free gift has a name")
        if not self.offered and (self.name is not None or self.community is not None):
            raise ValueError("a free gift that is not offered has no name")
        for value in (self.name, self.community):
            if value is None:
                continue
            if "|" in value:
                raise ValueError("free gift text cannot contain a pipe")
            lowered = value.casefold()
            if "http://" in lowered or "https://" in lowered or "checkout" in lowered:
                raise ValueError("free gift cannot carry a paid or external checkout link")
        return self


class NotificationDashboardBehaviour(ContractModel):
    """What the built notification dashboard actually does."""

    present: bool
    outputs: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def outputs_match_presence(self) -> Self:
        if self.present and not self.outputs:
            raise ValueError("a present notification dashboard names its outputs")
        if not self.present and self.outputs:
            raise ValueError("an absent notification dashboard has no outputs")
        if any("|" in output for output in self.outputs):
            raise ValueError("dashboard output cannot contain a pipe")
        return self


class BuiltVariant(ContractModel):
    """One colour variant that was actually built."""

    name: NonEmptyStr


class PriceSaleData(ContractModel):
    """Buyer price, anchor, and whether the anchor sits above the price."""

    currency: CurrencyCode
    price: PositiveDecimal
    anchor_price: PositiveDecimal
    quantity: PositiveInt
    sale_configured: bool

    @model_validator(mode="after")
    def anchor_matches_flag(self) -> Self:
        above = self.anchor_price > self.price
        if self.sale_configured is not above:
            raise ValueError("sale_configured must match an anchor above the price")
        if self.anchor_price < self.price:
            raise ValueError("anchor_price must be at least the listing price")
        return self


class CitedText(ContractModel):
    """Buyer-facing text that may only be the named template of its claims."""

    template_id: NonEmptyStr
    text: NonEmptyStr
    claim_ids: tuple[UUID, ...] = Field(min_length=1)


class DescriptionSection(ContractModel):
    """One of the eight playbook description roles."""

    role: DescriptionRole
    template_id: NonEmptyStr
    text: NonEmptyStr
    claim_ids: tuple[UUID, ...] = Field(min_length=1)


class ImageStripLine(ContractModel):
    """Copy for one of the ten listing-image frames."""

    role: ImageRole
    template_id: NonEmptyStr
    text: NonEmptyStr
    claim_ids: tuple[UUID, ...] = Field(min_length=1)


class VideoBeat(ContractModel):
    """One beat of the single walkthrough video."""

    role: VideoRole
    template_id: NonEmptyStr
    text: NonEmptyStr
    claim_ids: tuple[UUID, ...] = Field(min_length=1)


class ListingDraft(ContractModel):
    """Copy before claim validation. Tag and section counts are not yet enforced."""

    title: CitedText
    description_sections: tuple[DescriptionSection, ...]
    tags: tuple[CitedText, ...]
    hero_copy: CitedText
    image_strip: tuple[ImageStripLine, ...]
    video_sequence: tuple[VideoBeat, ...]
    price_sale: PriceSaleData
    claims: tuple[ListingClaim, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def media_and_claim_refs(self) -> Self:
        if tuple(line.role for line in self.image_strip) != IMAGE_ROLES:
            raise ValueError("image strip requires the ten playbook frames")
        if tuple(beat.role for beat in self.video_sequence) != VIDEO_BEATS:
            raise ValueError("video sequence requires the playbook beats")
        claim_ids = tuple(claim.claim_id for claim in self.claims)
        if len(set(claim_ids)) != len(claim_ids):
            raise ValueError("claim ids must be unique")
        known = set(claim_ids)
        cited = list(self.title.claim_ids)
        cited.extend(self.hero_copy.claim_ids)
        cited.extend(claim_id for tag in self.tags for claim_id in tag.claim_ids)
        cited.extend(
            claim_id for section in self.description_sections for claim_id in section.claim_ids
        )
        cited.extend(claim_id for line in self.image_strip for claim_id in line.claim_ids)
        cited.extend(claim_id for beat in self.video_sequence for claim_id in beat.claim_ids)
        if any(claim_id not in known for claim_id in cited):
            raise ValueError("copy cites a claim that is not on the draft")
        return self


class ListingCopy(ContractModel):
    """A draft that already matches the configured playbook shape."""

    draft: ListingDraft
    rules: ListingRules

    @model_validator(mode="after")
    def playbook_shape(self) -> Self:
        draft = self.draft
        rules = self.rules
        if len(IMAGE_ROLES) != rules.images:
            raise ValueError("configured image count does not match the playbook image strip")
        if len(draft.tags) != rules.tags:
            raise ValueError(f"listing requires exactly {rules.tags} tags")
        folded = tuple(normalize_tag(tag.text) for tag in draft.tags)
        if any(tag == "" for tag in folded):
            raise ValueError("listing tags must be non-empty")
        if any(len(tag) > ETSY_TAG_MAX for tag in folded):
            raise ValueError(f"listing tags must be at most {ETSY_TAG_MAX} characters")
        if len(set(folded)) != len(folded):
            raise ValueError("listing tags must be unique")
        roles = tuple(section.role for section in draft.description_sections)
        if roles != DESCRIPTION_ROLES:
            raise ValueError("listing description requires the eight playbook sections")
        if draft.price_sale.quantity != rules.quantity:
            raise ValueError("quantity must match listing rules")
        return self


class MerchandisingInput(ContractModel):
    """Everything A10 may read. Claims still have to cite a ProductFact."""

    spec: ProductSpec
    facts: tuple[ProductFact, ...] = Field(min_length=1)
    hubs: tuple[NonEmptyStr, ...]
    page_count: PositiveInt
    variants: tuple[BuiltVariant, ...] = Field(min_length=1)
    notification_dashboard: NotificationDashboardBehaviour
    shop_name: NonEmptyStr
    price: PositiveDecimal
    anchor_price: PositiveDecimal
    support: SupportConfig
    free_gift: FreeGiftConfig
    rules: ListingRules

    @model_validator(mode="after")
    def facts_belong_to_spec(self) -> Self:
        if self.anchor_price < self.price:
            raise ValueError("anchor_price must be at least the listing price")
        ids = tuple(fact.fact_id for fact in self.facts)
        if len(set(ids)) != len(ids):
            raise ValueError("fact ids must be unique")
        keys = tuple(fact.fact_key for fact in self.facts)
        if len(set(keys)) != len(keys):
            raise ValueError("fact keys must be unique")
        for fact in self.facts:
            if fact.product_id != self.spec.product_id or fact.spec_id != self.spec.spec_id:
                raise ValueError("fact does not belong to this product spec")
        return self


def fact_items(value: str) -> tuple[str, ...]:
    """Split a pipe-joined fact. A value with no pipe is one item."""
    return tuple(value.split("|"))


def encode_support(config: SupportConfig) -> str:
    """Canonical support fact value."""
    if not config.offered:
        return "not_offered"
    return f"offered|{config.channel}"


def encode_free_gift(config: FreeGiftConfig) -> str:
    """Canonical free-gift fact value."""
    if not config.offered:
        return "not_offered"
    if config.community is None:
        return f"offered|{config.name}"
    return f"offered|{config.name}|{config.community}"


def encode_dashboard(behaviour: NotificationDashboardBehaviour) -> str:
    """Canonical notification-dashboard fact value."""
    if not behaviour.present:
        return "absent"
    return "|".join(behaviour.outputs)


def money_text(amount: Decimal) -> str:
    """Stable decimal text for a price fact."""
    return format(amount, "f")
