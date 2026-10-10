"""Fact-bound claim validation for A10 listing copy.

Each rejection class is its own function. ``validate_claims`` calls them by
name so a test can delete one call and show that class is no longer rejected.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from re import Pattern
from typing import Final
from uuid import UUID

from money_machine.agents.contracts.merchandising import (
    DESCRIPTION_ROLES,
    ETSY_TAG_MAX,
    ClaimCorrection,
    ClaimKind,
    ListingClaim,
    ListingDraft,
    MerchandisingInput,
    ProductFact,
    RejectionClass,
    fact_items,
)
from money_machine.domain.services.listing_text import (
    TextSlot,
    has_concealment,
    normalize_tag,
    normalize_text,
    render,
    script_rejected,
)

_NUMBER_WORDS: Final[str] = (
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    "fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|"
    "fifty|sixty|seventy|eighty|ninety|hundred|thousand"
)
_PAGE_UNIT: Final[str] = r"(?:printable\s+|bonus\s+)?(?:pp|pages?)\b"
_PAGE_NUMBERS: Final[Pattern[str]] = re.compile(
    rf"(?<!\d)(\d+)\s*[+\-]?\s*{_PAGE_UNIT}"
    rf"|\b((?:(?:over|plus)\s+)?(?:{_NUMBER_WORDS})(?:[\s\-]+(?:{_NUMBER_WORDS}))*)"
    rf"[\s\-]+{_PAGE_UNIT}",
    re.IGNORECASE,
)
# A layout span ("one page per day", "4 page weekly layout") says how a spread
# is laid out, not how big the product is: a singular "page" of at most twelve,
# then an optional cadence word, then a layout noun.
_LAYOUT_COUNT: Final[Pattern[str]] = re.compile(
    r"(?:[1-9]|1[0-2]|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
    r"[\s\-]+page"
)
_LAYOUT_TAIL: Final[Pattern[str]] = re.compile(
    r"[\s\-]+(?:(?:daily|weekly|monthly|yearly|annual)\s+)?"
    r"(?:per|layouts?|spreads?|summary|summaries|views?|overviews?)\b"
)
_AUTOMATION: Final[Pattern[str]] = re.compile(
    r"\bautomat(?!ic\s+savings\b)\w*|\bauto-[\w-]+|\bunattended\b|\bhands[-\s]free\b"
    r"|\bautofill\w*",
    re.IGNORECASE,
)
_REVIEW: Final[Pattern[str]] = re.compile(
    r"\btop[-\s]?rated\b|\bhighly reviewed\b|\btestimonials?\b|\brated\b|\bfive-star\b"
    r"|\braves?\b"
    r"|\b(?:\d[\d,]*|five|four|three|two|one)[\s-]*stars?\b"
    r"|\bstars?[\s-]+reviews?\b"
    r"|\d[\d,.]*\+?\s*(?:(?:average|avg\.?|customer|buyer|verified)\s+)?(?:reviews?|ratings?)\b"
    r"|\b(?:reviews?|ratings?)\s*[:=]?\s*\d"
    r"|\baverage\s+(?:reviews?|ratings?)\b",
    re.IGNORECASE,
)
_SALES: Final[Pattern[str]] = re.compile(
    r"\bbest[-\s]?sell(?:ers?|ing)\b"
    r"|\bunits sold\b|\d[\d,]*\+?\s+sold\b|\d[\d,]*\+?\s+downloads\b|\d+\s*k\s+downloads\b"
    r"|(?:^|[^\w\s]\s*|\b(?:the|our|your|a|an|is|rated|ranked|voted|etsy|amazon)\s+|\w['\u2019]s?\s+)"
    r"#\s*1(?!\d)"
    r"|\d[\d,]*\+?\s+orders\b|\borders on file\b",
    re.IGNORECASE,
)
_TRUST: Final[Pattern[str]] = re.compile(
    r"\btrust bars?\b|\btrusted by\b|\bas seen (?:in|on)\b|\bmoney[-\s]back\b"
    r"|\bfeatured in\b|\bsatisfaction guaranteed\b",
    re.IGNORECASE,
)
_SOCIAL: Final[Pattern[str]] = re.compile(
    r"\bcustomers love\b|\busers say\b|\bthousands of\b|\bcommunity of\s+\d+|\bloved by\b"
    r"|\d[\d,]*\+?\s+happy customers\b"
    r"|\bjoin\s+\d[\d,]*(?![\d,])\+?(?![+\s-]*(?:days?|weeks?|months?|minutes?|hours?)\b)",
    re.IGNORECASE,
)
_URL: Final[Pattern[str]] = re.compile(r"https?://|www\.", re.IGNORECASE)
_CLASS_FACT: Final[tuple[tuple[str, Pattern[str]], ...]] = (
    ("automation", _AUTOMATION),
    ("reviews", _REVIEW),
    ("sales_count", _SALES),
    ("trust_bar", _TRUST),
    ("social_proof", _SOCIAL),
)
_SPECIAL_KINDS: Final[frozenset[ClaimKind]] = frozenset(
    {
        "page_count",
        "feature",
        "variant",
        "automation",
        "review",
        "sales_performance",
        "trust_bar",
        "social_proof",
    }
)
_LIST_KINDS: Final[frozenset[ClaimKind]] = frozenset(
    {"feature", "variant", "hub", "device", "database"}
)
_ROLE_TEMPLATE: Final[dict[str, str]] = {
    "hook": "hook",
    "included": "included",
    "audience": "audience",
    "how_it_works": "access_line",
    "features": "features",
    "variants": "variant_devices",
    "support": "support",
    "offer": "offer",
    "hero": "hero",
    "overview": "overview",
    "hub_1": "hub_frame",
    "hub_2": "hub_frame",
    "hub_3": "hub_frame",
    "hub_4": "hub_frame",
    "hub_5": "hub_frame",
    "colour_options": "variant_line",
    "devices": "device_line",
    "dashboard": "video_dashboard",
    "notification_panel": "video_notification",
    "strongest_hubs": "video_hubs",
    "duplication_access": "access_line",
}
TAG_KINDS: Final[frozenset[ClaimKind]] = frozenset(
    {"identity", "category", "feature", "variant", "shop", "hub", "device"}
)
_KIND_KEY: Final[dict[ClaimKind, str]] = {
    "page_count": "page_count",
    "feature": "features",
    "variant": "colour_names",
    "automation": "automation",
    "review": "reviews",
    "sales_performance": "sales_count",
    "trust_bar": "trust_bar",
    "social_proof": "social_proof",
    "hub": "hubs",
    "dashboard": "dashboard_outputs",
    "device": "supported_devices",
    "price": "price",
    "anchor": "anchor_price",
    "currency": "currency",
    "support": "support",
    "free_gift": "free_gift",
    "shop": "shop_name",
    "identity": "identity",
    "category": "base_category",
    "buyer_problem": "buyer_problem",
    "database": "databases",
    "access": "secret_links",
}


@dataclass(frozen=True, slots=True)
class ClaimValidation:
    """Pass only when every checked claim and the playbook shape hold."""

    passed: bool
    corrections: tuple[ClaimCorrection, ...]


def page_counts(folded: str) -> tuple[re.Match[str], ...]:
    """Page-count mentions in folded text, leaving out layout spans."""
    return tuple(match for match in _PAGE_NUMBERS.finditer(folded) if not _layout_span(match))


def _layout_span(match: re.Match[str]) -> bool:
    text = match.group(0)
    if _LAYOUT_COUNT.fullmatch(text) is None:
        return False
    return _LAYOUT_TAIL.match(match.string, match.end()) is not None


def fact_text_problem(key: str, value: str) -> str | None:
    """Why this fact must not be rendered, or None when the value may be shown.

    A class fact is exempt from its own pattern, so the recorded statement can
    still be cited. Every other fact is scanned, including page counts.
    """
    if has_concealment(value) or script_rejected(value):
        return "concealed"
    if key != "secret_links" and _URL.search(value) is not None:
        return "url"
    folded = normalize_text(value)
    if key != "page_count" and page_counts(folded):
        return "page"
    for fact_key, pattern in _CLASS_FACT:
        if key == fact_key:
            continue
        if pattern.search(folded) is not None:
            return "class"
    return None


def validate_claims(copy: ListingDraft, request: MerchandisingInput) -> ClaimValidation:
    """Run every claim rule. One deleted call stops rejecting that class."""
    corrections: list[ClaimCorrection] = []
    corrections.extend(reject_unknown_fact(copy, request))
    corrections.extend(reject_invented_page_count(copy, request))
    corrections.extend(reject_nonexistent_feature(copy, request))
    corrections.extend(reject_variant_not_built(copy, request))
    corrections.extend(reject_unsupported_automation(copy, request))
    corrections.extend(reject_invented_review(copy, request))
    corrections.extend(reject_invented_sales(copy, request))
    corrections.extend(reject_invented_trust_bar(copy, request))
    corrections.extend(reject_unsupported_social_proof(copy, request))
    corrections.extend(reject_unmatched_statement(copy, request))
    corrections.extend(reject_unbound_text(copy, request))
    corrections.extend(reject_mixed_script(copy, request))
    corrections.extend(reject_tag_count(copy, request))
    corrections.extend(reject_section_count(copy, request))
    return ClaimValidation(passed=len(corrections) == 0, corrections=tuple(corrections))


def reject_unknown_fact(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject a claim whose fact id is not one of the supplied ProductFacts."""
    known = {fact.fact_id for fact in request.facts}
    corrections: list[ClaimCorrection] = []
    for claim in copy.claims:
        if claim.fact_id in known:
            continue
        corrections.append(
            _issue(
                claim,
                "unknown_fact",
                claim.fact_id,
                (
                    f"unknown_fact: claim {claim.claim_id} cites {claim.fact_id} "
                    "which is not a ProductFact on this product"
                ),
            )
        )
    return tuple(corrections)


def reject_invented_page_count(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject a page count that is not the built count and the page_count fact."""
    actual = str(request.page_count)
    corrections = _reject_special(
        copy,
        request,
        kind="page_count",
        rejection_class="invented_page_count",
        list_valued=False,
        actual_values=(actual,),
        prose_pattern=None,
    )
    found = list(corrections)
    fact = _by_key(request, "page_count")
    for text, claim_ids, _template, _required in _bound_surfaces(copy):
        folded = normalize_text(text)
        holders = _holding_values(copy, request, claim_ids, "page_count")
        for match in page_counts(folded):
            digits = match.group(1)
            number = digits if digits is not None else match.group(0)
            licensed = any(normalize_text(item) == number for item in holders)
            if licensed:
                continue
            anchor = _first(copy, "page_count")
            found.append(
                ClaimCorrection(
                    claim_id=anchor.claim_id if anchor is not None else UUID(int=0),
                    rejection_class="invented_page_count",
                    fact_id=None if fact is None else fact.fact_id,
                    correction=(
                        f"invented_page_count: prose states {number} pages; "
                        f"built page count is {actual}"
                    ),
                )
            )
            break
    return tuple(found)


def reject_nonexistent_feature(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject a feature that is not one spec feature, item for item."""
    return _reject_special(
        copy,
        request,
        kind="feature",
        rejection_class="nonexistent_feature",
        list_valued=True,
        actual_values=tuple(request.spec.features),
        prose_pattern=None,
    )


def reject_variant_not_built(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject a variant name that was not actually built."""
    built = tuple(variant.name for variant in request.variants)
    return _reject_special(
        copy,
        request,
        kind="variant",
        rejection_class="variant_not_built",
        list_valued=True,
        actual_values=built,
        prose_pattern=None,
    )


def reject_unsupported_automation(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject automation the automation fact does not state."""
    return _reject_special(
        copy,
        request,
        kind="automation",
        rejection_class="unsupported_automation",
        list_valued=False,
        actual_values=None,
        prose_pattern=_AUTOMATION,
    )


def reject_invented_review(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject review language that is not the reviews fact."""
    return _reject_special(
        copy,
        request,
        kind="review",
        rejection_class="invented_review",
        list_valued=False,
        actual_values=None,
        prose_pattern=_REVIEW,
    )


def reject_invented_sales(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject sales performance that is not the sales_count fact."""
    return _reject_special(
        copy,
        request,
        kind="sales_performance",
        rejection_class="invented_sales",
        list_valued=False,
        actual_values=None,
        prose_pattern=_SALES,
    )


def reject_invented_trust_bar(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject a trust bar that is not the trust_bar fact."""
    return _reject_special(
        copy,
        request,
        kind="trust_bar",
        rejection_class="invented_trust_bar",
        list_valued=False,
        actual_values=None,
        prose_pattern=_TRUST,
    )


def reject_unsupported_social_proof(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject social proof that is not the social_proof fact."""
    return _reject_special(
        copy,
        request,
        kind="social_proof",
        rejection_class="unsupported_social_proof",
        list_valued=False,
        actual_values=None,
        prose_pattern=_SOCIAL,
    )


def reject_unmatched_statement(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject an ordinary claim whose statement is not the cited fact.

    The eight rejection classes are handled by their own functions. This rule
    does not second-guess them.
    """
    corrections: list[ClaimCorrection] = []
    for claim in copy.claims:
        if claim.kind in _SPECIAL_KINDS:
            continue
        cited = _by_id(request, claim.fact_id)
        if cited is None:
            continue
        if _statement_matches(claim, cited):
            continue
        corrections.append(
            _issue(
                claim,
                "unknown_fact",
                cited.fact_id,
                (
                    f"unknown_fact: claim {claim.claim_id} states {claim.stated_value!r} "
                    f"which is not fact {cited.fact_id} ({cited.fact_key})"
                ),
            )
        )
    return tuple(corrections)


def reject_unbound_text(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject buyer-facing text that is not the template of its cited facts."""
    corrections: list[ClaimCorrection] = []
    by_id = {claim.claim_id: claim for claim in copy.claims}
    for text, claim_ids, template_id, required in _bound_surfaces(copy):
        if has_concealment(text):
            corrections.append(
                _surface_issue(
                    copy,
                    claim_ids,
                    f"unbound_text: {template_id} hides characters in the cited facts",
                )
            )
            continue
        cited = _resolve(by_id, claim_ids)
        if cited is not None and any(not _holds(claim, request) for claim in cited):
            continue
        if required == "tag" and cited is not None and not _tag_kind_allowed(cited):
            corrections.append(
                _surface_issue(
                    copy,
                    claim_ids,
                    "unbound_text: tag kind is not a tag fact",
                )
            )
            continue
        slots = (
            ()
            if cited is None
            else tuple(TextSlot(claim.kind, claim.stated_value) for claim in cited)
        )
        expected = None
        if cited is not None and template_id == required:
            expected = _render_or_none(template_id, slots, request.rules.quantity)
        if expected is not None and normalize_text(text) == normalize_text(expected):
            continue
        corrections.append(
            _surface_issue(
                copy,
                claim_ids,
                f"unbound_text: {template_id} is not the cited fact template",
            )
        )
    return tuple(corrections)


def reject_mixed_script(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject a Latin sentence that hides a non-Latin letter."""
    del request
    corrections: list[ClaimCorrection] = []
    for text, claim_ids, template_id, _required in _bound_surfaces(copy):
        if not script_rejected(text):
            continue
        corrections.append(
            _surface_issue(
                copy,
                claim_ids,
                f"unbound_text: {template_id} mixes a non-Latin letter into Latin text",
            )
        )
    return tuple(corrections)


def reject_tag_count(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject a tag list that is not the configured count of unique short tags."""
    expected = request.rules.tags
    tags = copy.tags
    normalized = tuple(normalize_tag(tag.text) for tag in tags)
    too_long = any(len(tag) > ETSY_TAG_MAX for tag in normalized)
    empty = any(tag == "" for tag in normalized)
    duplicate = len(set(normalized)) != len(normalized)
    if len(tags) == expected and not duplicate and not too_long and not empty:
        return ()
    anchor = copy.claims[0]
    return (
        ClaimCorrection(
            claim_id=anchor.claim_id,
            rejection_class="tag_count",
            fact_id=None,
            correction=(
                f"tag_count: listing requires exactly {expected} unique tags "
                f"of at most {ETSY_TAG_MAX} characters, got {len(tags)}"
            ),
        ),
    )


def reject_section_count(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject a description that is not the eight playbook roles in order."""
    del request
    roles = tuple(section.role for section in copy.description_sections)
    if roles == DESCRIPTION_ROLES:
        return ()
    anchor = copy.claims[0]
    return (
        ClaimCorrection(
            claim_id=anchor.claim_id,
            rejection_class="section_count",
            fact_id=None,
            correction=(
                "section_count: description requires exactly these eight sections in order: "
                + ", ".join(DESCRIPTION_ROLES)
            ),
        ),
    )


def _reject_special(
    copy: ListingDraft,
    request: MerchandisingInput,
    *,
    kind: ClaimKind,
    rejection_class: RejectionClass,
    list_valued: bool,
    actual_values: Sequence[str] | None,
    prose_pattern: Pattern[str] | None,
) -> tuple[ClaimCorrection, ...]:
    corrections: list[ClaimCorrection] = []
    for claim in copy.claims:
        if claim.kind != kind:
            continue
        cited = _by_id(request, claim.fact_id)
        if cited is None:
            continue
        if _kind_matches(claim, cited, list_valued=list_valued, actual_values=actual_values):
            continue
        corrections.append(
            _issue(
                claim,
                rejection_class,
                cited.fact_id,
                (
                    f"{rejection_class}: claim {claim.claim_id} states {claim.stated_value!r}; "
                    f"fact {cited.fact_id} ({cited.fact_key}) is {cited.fact_value!r}"
                ),
            )
        )
    if prose_pattern is None:
        return tuple(corrections)
    for text, claim_ids, _template, _required in _bound_surfaces(copy):
        folded = normalize_text(text)
        cited = _holding_values(copy, request, claim_ids, kind)
        for match in prose_pattern.finditer(folded):
            if _span_inside(match.group(0), cited):
                continue
            anchor = _first(copy, kind)
            corrections.append(
                ClaimCorrection(
                    claim_id=anchor.claim_id if anchor is not None else UUID(int=0),
                    rejection_class=rejection_class,
                    fact_id=None if anchor is None else anchor.fact_id,
                    correction=(
                        f"{rejection_class}: prose makes that claim without a matching ProductFact"
                    ),
                )
            )
            break
    return tuple(corrections)


def _tag_kind_allowed(cited: tuple[ListingClaim, ...]) -> bool:
    return len(cited) == 1 and cited[0].kind in TAG_KINDS


def _kind_matches(
    claim: ListingClaim,
    cited: ProductFact,
    *,
    list_valued: bool,
    actual_values: Sequence[str] | None,
) -> bool:
    expected = _KIND_KEY[claim.kind]
    if cited.fact_key != expected:
        return False
    if not _fact_sourced(claim.kind, cited, actual_values):
        return False
    if list_valued:
        allowed = claim.stated_value in fact_items(cited.fact_value)
    else:
        allowed = claim.stated_value == cited.fact_value
    return allowed


def _statement_matches(claim: ListingClaim, cited: ProductFact) -> bool:
    expected = _KIND_KEY[claim.kind]
    if cited.fact_key != expected:
        return False
    if claim.kind in _LIST_KINDS:
        return claim.stated_value in fact_items(cited.fact_value)
    return claim.stated_value == cited.fact_value


def _by_id(request: MerchandisingInput, fact_id: UUID) -> ProductFact | None:
    for fact in request.facts:
        if fact.fact_id == fact_id:
            return fact
    return None


def _by_key(request: MerchandisingInput, key: str) -> ProductFact | None:
    for fact in request.facts:
        if fact.fact_key == key:
            return fact
    return None


def _first(copy: ListingDraft, kind: ClaimKind) -> ListingClaim | None:
    for claim in copy.claims:
        if claim.kind == kind:
            return claim
    return None


def _bound_surfaces(
    copy: ListingDraft,
) -> tuple[tuple[str, tuple[UUID, ...], str, str], ...]:
    rows: list[tuple[str, tuple[UUID, ...], str, str]] = [
        (copy.title.text, copy.title.claim_ids, copy.title.template_id, "title"),
        (copy.hero_copy.text, copy.hero_copy.claim_ids, copy.hero_copy.template_id, "hero"),
    ]
    rows.extend(
        (item.text, item.claim_ids, item.template_id, _ROLE_TEMPLATE[item.role])
        for item in copy.description_sections
    )
    rows.extend(
        (item.text, item.claim_ids, item.template_id, _ROLE_TEMPLATE[item.role])
        for item in copy.image_strip
    )
    rows.extend(
        (item.text, item.claim_ids, item.template_id, _ROLE_TEMPLATE[item.role])
        for item in copy.video_sequence
    )
    rows.extend((item.text, item.claim_ids, item.template_id, "tag") for item in copy.tags)
    return tuple(rows)


def _resolve(
    by_id: dict[UUID, ListingClaim],
    claim_ids: tuple[UUID, ...],
) -> tuple[ListingClaim, ...] | None:
    if not claim_ids:
        return None
    found: list[ListingClaim] = []
    for claim_id in claim_ids:
        claim = by_id.get(claim_id)
        if claim is None:
            return None
        found.append(claim)
    return tuple(found)


def _holds(claim: ListingClaim, request: MerchandisingInput) -> bool:
    cited = _by_id(request, claim.fact_id)
    if cited is None:
        return False
    if claim.kind in _SPECIAL_KINDS:
        return _kind_matches(
            claim,
            cited,
            list_valued=claim.kind in _LIST_KINDS,
            actual_values=_actual_for(claim.kind, request),
        )
    return _statement_matches(claim, cited)


def _actual_for(kind: ClaimKind, request: MerchandisingInput) -> tuple[str, ...] | None:
    if kind == "page_count":
        return (str(request.page_count),)
    if kind == "variant":
        return tuple(variant.name for variant in request.variants)
    if kind == "feature":
        return tuple(request.spec.features)
    return None


def _fact_sourced(
    kind: ClaimKind,
    cited: ProductFact,
    actual_values: Sequence[str] | None,
) -> bool:
    """The cited fact itself matches the built source, before the stated value is read."""
    if actual_values is None:
        return True
    if kind in _LIST_KINDS:
        return fact_items(cited.fact_value) == tuple(actual_values)
    return cited.fact_value in tuple(actual_values)


def _holding_values(
    copy: ListingDraft,
    request: MerchandisingInput,
    claim_ids: tuple[UUID, ...],
    kind: ClaimKind,
) -> tuple[str, ...]:
    by_id = {claim.claim_id: claim for claim in copy.claims}
    values: list[str] = []
    for claim_id in claim_ids:
        claim = by_id.get(claim_id)
        if claim is not None and claim.kind == kind and _holds(claim, request):
            values.append(claim.stated_value)
    return tuple(values)


def _span_inside(span: str, values: tuple[str, ...]) -> bool:
    needle = normalize_text(span)
    if needle == "":
        return False
    return any(needle in normalize_text(value) for value in values)


def _render_or_none(template_id: str, slots: tuple[TextSlot, ...], quantity: int) -> str | None:
    try:
        return render(template_id, slots, quantity=quantity)
    except ValueError:
        return None


def _surface_issue(
    copy: ListingDraft,
    claim_ids: tuple[UUID, ...],
    correction: str,
) -> ClaimCorrection:
    by_id = {claim.claim_id: claim for claim in copy.claims}
    anchor = by_id.get(claim_ids[0]) if claim_ids else None
    if anchor is None and copy.claims:
        anchor = copy.claims[0]
    return ClaimCorrection(
        claim_id=anchor.claim_id if anchor is not None else UUID(int=0),
        rejection_class="unbound_text",
        fact_id=None if anchor is None else anchor.fact_id,
        correction=correction,
    )


def _issue(
    claim: ListingClaim,
    rejection_class: RejectionClass,
    fact_id: UUID | None,
    correction: str,
) -> ClaimCorrection:
    return ClaimCorrection(
        claim_id=claim.claim_id,
        rejection_class=rejection_class,
        fact_id=fact_id,
        correction=correction,
    )
