from money_machine.domain.services.claim_validation import AdmittedFact, ClaimValidationService

FACTS = (
    "Includes six navigation hubs",
    "Includes linked course and task views",
    "Available in ink, sand, and sage colour variants",
)


def test_exact_facts_and_structural_copy_are_bound_deterministically() -> None:
    result = ClaimValidationService().validate(
        (
            "Includes linked course and task views",
            "A digital planner for students",
        ),
        FACTS,
        admitted_facts=(
            AdmittedFact(
                claim="Includes linked course and task views",
                category="FEATURE",
                evidence_ids=("evidence-1",),
            ),
        ),
        structural_claims=("A digital planner for students",),
    )

    assert result.passed is True
    assert result.records[0].fact_index == 1
    assert result.records[0].source == "PRODUCT_FACT"
    assert result.records[1].source == "STRUCTURAL_COPY"


def test_unsupported_claim_categories_fail_with_stable_reason_codes() -> None:
    claims = (
        "The best planner on Etsy",
        "Trusted by 10,000 students",
        "Save 20 hours every week",
        "Works on every device",
        "Customers love this planner",
    )

    result = ClaimValidationService().validate(claims, FACTS)

    assert result.passed is False
    assert all(record.reason_code == "UNBOUND_PRODUCT_CLAIM" for record in result.records)


def test_marketplace_evidence_is_not_promoted_to_a_product_fact() -> None:
    result = ClaimValidationService().validate(
        ("Competing planners have thousands of reviews",),
        FACTS,
    )

    assert result.passed is False
    assert result.records[0].reason_code == "UNBOUND_PRODUCT_CLAIM"


def test_prohibited_claims_are_rejected_even_when_copied_into_product_facts() -> None:
    claims = (
        "Competing planners have thousands of reviews",
        "The ultimate planner",
        "A bestseller with proven demand",
        "Save 20 hours every week",
        "Compatible with all devices",
        "Rated five stars by customers",
    )

    result = ClaimValidationService().validate(claims, claims)

    assert result.passed is False
    assert all(record.reason_code == "UNADMITTED_PRODUCT_FACT" for record in result.records)


def test_platform_and_version_compatibility_cannot_self_authorize_as_facts() -> None:
    claims = (
        "Works on Windows and macOS",
        "Works with iOS 18",
        "Compatible with Chrome version 140",
        "Runs on desktop and mobile devices",
    )

    result = ClaimValidationService().validate(claims, claims)

    assert result.passed is False
    assert all(record.source == "REJECTED" for record in result.records)
    assert all(record.reason_code == "UNADMITTED_PRODUCT_FACT" for record in result.records)


def test_revenue_claims_cannot_self_authorize_as_plain_product_facts() -> None:
    claims = ("Earns $500 monthly", "Produces recurring revenue")

    result = ClaimValidationService().validate(claims, claims)

    assert result.passed is False
    assert all(record.source == "REJECTED" for record in result.records)
    assert all(record.reason_code == "UNADMITTED_PRODUCT_FACT" for record in result.records)


def test_adversarial_compatibility_and_passive_income_facts_are_rejected() -> None:
    claims = (
        "Supports Excel 365",
        "Built for Notion 2.0",
        "Requires Adobe Acrobat 2025",
        "Generate passive cash flow",
        "Pays for itself",
    )

    result = ClaimValidationService().validate(claims, claims)

    assert result.passed is False
    assert all(record.reason_code == "UNADMITTED_PRODUCT_FACT" for record in result.records)


def test_untyped_product_facts_cannot_self_admit_semantic_or_unicode_paraphrases() -> None:
    claims = (
        "Optimized for Microsoft 365",
        "Integrates seamlessly with Nоtion",  # noqa: RUF001 - adversarial Unicode
        "Designed for Photoshop 2026",
        "Excel‑ready for finance teams",  # noqa: RUF001 - adversarial Unicode
        "Compatible across all major platforms",
        "Turns templates into ｃａｓｈ",  # noqa: RUF001 - adversarial Unicode
        "Boosts your bottom line",
        "A profitable digital product",
        "Recoups its purchase cost",
        "Creates a new money stream",
    )

    result = ClaimValidationService().validate(claims, claims)

    assert result.passed is False
    assert all(record.source == "REJECTED" for record in result.records)
    assert all(record.reason_code == "UNADMITTED_PRODUCT_FACT" for record in result.records)
