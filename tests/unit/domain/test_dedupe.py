from __future__ import annotations

from typing import cast

import pytest

from money_machine.domain.models.product_spec import ProductFact, ProductSpec
from money_machine.domain.services.dedupe import DedupeService
from money_machine.domain.value_objects import canonical_sha256


def _spec(spec_id: str, niche: str, category: str) -> ProductSpec:
    target_buyer = f"People managing {niche}"
    promised_outcome = f"A structured {category} workspace"
    product_facts = (
        ProductFact(
            claim="Configured with 6 hubs",
            category="HUB_INVENTORY",
            evidence_ids=("EVD-001",),
        ),
        ProductFact(
            claim="Includes Structured navigation",
            category="FEATURE",
            evidence_ids=("EVD-001",),
        ),
        ProductFact(
            claim="Configured with 3 colour variants",
            category="COLOUR_VARIANTS",
            evidence_ids=("EVD-001",),
        ),
        ProductFact(
            claim=target_buyer,
            category="BUYER_FIT",
            evidence_ids=("EVD-001",),
        ),
        ProductFact(
            claim=promised_outcome,
            category="WORKFLOW_OUTCOME",
            evidence_ids=("EVD-001",),
        ),
    )
    body: dict[str, object] = {
        "candidate_id": f"C-{spec_id}",
        "identity_niche": niche,
        "base_category": category,
        "target_buyer": target_buyer,
        "promised_outcome": promised_outcome,
        "hubs": ["Home", "Plan", "Track", "Review", "Library", "Settings"],
        "colour_variants": ["Ink", "Sage", "Sand"],
        "features": ["Structured navigation"],
        "product_facts": tuple(fact.model_dump(mode="json") for fact in product_facts),
        "source_evidence_ids": ["EVD-001"],
    }
    return ProductSpec(
        product_spec_id=spec_id,
        candidate_id=f"C-{spec_id}",
        identity_niche=niche,
        base_category=category,
        target_buyer=target_buyer,
        promised_outcome=promised_outcome,
        hubs=("Home", "Plan", "Track", "Review", "Library", "Settings"),
        colour_variants=("Ink", "Sage", "Sand"),
        features=("Structured navigation",),
        product_facts=product_facts,
        source_evidence_ids=("EVD-001",),
        spec_sha256=canonical_sha256(body),
    )


def test_dedupe_rejects_exact_normalized_identity_and_category() -> None:
    candidate = _spec("PS-new", "Budget Moms", "Planner")
    existing = _spec("PS-old", " budget—MOMS ", "PLANNER")
    result = DedupeService().evaluate(candidate, (existing,))
    assert not result.passed
    assert result.matched_product_spec_ids == ("PS-old",)
    assert "identity_category_match" in result.reasons


def test_dedupe_rejects_title_token_overlap_at_inclusive_threshold() -> None:
    candidate = _spec("PS-new", "alpha beta gamma delta epsilon zeta eta theta", "iota kappa")
    existing = _spec("PS-old", "alpha beta gamma delta epsilon zeta eta lambda", "mu nu")
    result = DedupeService(stop_words=()).evaluate(candidate, (existing,))
    assert not result.passed
    assert "title_token_overlap:0.700" in result.reasons


@pytest.mark.parametrize("separator", ["_", "\N{FULLWIDTH LOW LINE}", "—"])
def test_dedupe_removes_ascii_and_unicode_punctuation_before_overlap(
    separator: str,
) -> None:
    candidate = _spec(
        "PS-new",
        f"alpha{separator}beta gamma delta epsilon zeta eta theta",
        "iota kappa",
    )
    existing = _spec("PS-old", "alpha beta gamma delta epsilon zeta eta theta lambda", "mu")
    result = DedupeService(stop_words=()).evaluate(candidate, (existing,))
    assert not result.passed
    assert "title_token_overlap:0.800" in result.reasons


def test_dedupe_accepts_title_token_overlap_below_threshold() -> None:
    candidate = _spec("PS-new", "alpha beta gamma delta epsilon zeta eta theta", "iota kappa")
    existing = _spec("PS-old", "alpha beta gamma delta epsilon zeta lambda mu", "nu xi")
    result = DedupeService(stop_words=()).evaluate(candidate, (existing,))
    assert result.passed


def test_dedupe_accepts_lower_overlap_and_emits_compared_identities() -> None:
    candidate = _spec("PS-new", "Budget Moms Planner", "Finance")
    existing = _spec("PS-old", "Wedding Photographer CRM", "Business")
    result = DedupeService().evaluate(candidate, (existing,))
    assert result.passed
    assert result.matched_product_spec_ids == ()
    assert result.reasons == ("compared:PS-old",)
    body = cast(
        dict[str, object],
        result.model_dump(exclude={"dedupe_result_id", "result_sha256"}),
    )
    assert result.result_sha256 == canonical_sha256(body)
