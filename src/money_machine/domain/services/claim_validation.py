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

_PAGE_NUMBERS: Final[Pattern[str]] = re.compile(r"(?<!\d)(\d+)\s+pages?\b", re.IGNORECASE)
_AUTOMATION: Final[Pattern[str]] = re.compile(
    r"\b(automat\w*|auto-[\w-]+|unattended)\b",
    re.IGNORECASE,
)
_REVIEW: Final[Pattern[str]] = re.compile(
    r"\b(reviews?|ratings?|stars?|testimonials?)\b",
    re.IGNORECASE,
)
_SALES: Final[Pattern[str]] = re.compile(
    r"\b(bestsellers?|best-sellers?|best sellers?|units sold|\d[\d,]*\s+sold|orders)\b",
    re.IGNORECASE,
)
_TRUST: Final[Pattern[str]] = re.compile(
    r"(trust bars?|trusted by|as seen in|money-back)",
    re.IGNORECASE,
)
_SOCIAL: Final[Pattern[str]] = re.compile(
    r"(customers love|users say|thousands of|community of\s+\d+)",
    re.IGNORECASE,
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
    for number in _PAGE_NUMBERS.findall(_prose(copy)):
        if number == actual:
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
    return tuple(found)


def reject_nonexistent_feature(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject a feature that is not listed on the features fact."""
    return _reject_special(
        copy,
        request,
        kind="feature",
        rejection_class="nonexistent_feature",
        list_valued=True,
        actual_values=None,
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


def reject_tag_count(
    copy: ListingDraft,
    request: MerchandisingInput,
) -> tuple[ClaimCorrection, ...]:
    """Reject a tag list that is not the configured count of unique short tags."""
    expected = request.rules.tags
    tags = copy.tags
    folded = tuple(tag.casefold() for tag in tags)
    too_long = any(len(tag) > ETSY_TAG_MAX for tag in tags)
    if len(tags) == expected and len(set(folded)) == len(folded) and not too_long:
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
    prose_hit = prose_pattern is not None and prose_pattern.search(_prose(copy))
    if prose_hit and not _has_passing(copy, request, kind, list_valued, actual_values):
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
    return tuple(corrections)


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
    if list_valued:
        allowed = claim.stated_value in fact_items(cited.fact_value)
    else:
        allowed = claim.stated_value == cited.fact_value
    if not allowed:
        return False
    return actual_values is None or claim.stated_value in actual_values


def _statement_matches(claim: ListingClaim, cited: ProductFact) -> bool:
    expected = _KIND_KEY[claim.kind]
    if cited.fact_key != expected:
        return False
    if claim.kind in _LIST_KINDS:
        return claim.stated_value in fact_items(cited.fact_value)
    return claim.stated_value == cited.fact_value


def _has_passing(
    copy: ListingDraft,
    request: MerchandisingInput,
    kind: ClaimKind,
    list_valued: bool,
    actual_values: Sequence[str] | None,
) -> bool:
    for claim in copy.claims:
        if claim.kind != kind:
            continue
        cited = _by_id(request, claim.fact_id)
        if cited is None:
            continue
        if _kind_matches(claim, cited, list_valued=list_valued, actual_values=actual_values):
            return True
    return False


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


def _prose(copy: ListingDraft) -> str:
    parts = [copy.title, copy.hero_copy, copy.price_sale.currency]
    parts.extend(section.text for section in copy.description_sections)
    parts.extend(line.text for line in copy.image_strip)
    parts.extend(beat.text for beat in copy.video_sequence)
    parts.extend(copy.tags)
    parts.extend(claim.stated_value for claim in copy.claims)
    return "\n".join(parts)


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
