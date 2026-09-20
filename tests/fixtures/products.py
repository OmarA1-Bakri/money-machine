"""Fixture generators for product domain models (ProductSpec, TeardownReport, etc).

These fixtures support testing without real competitor IP or live external data.
Per D-0017 and Session 05 Lane 4 scope: simulation only, no copying.
"""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID, uuid4

from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.products import (
    ProductSpec,
    ResearchObservation,
    ResearchReport,
    TeardownReport,
)
from money_machine.domain.models.rules import ProductShapeRules


def create_fixture_product_shape_rules() -> ProductShapeRules:
    """Create default ProductShapeRules per workbook §7 / D-0022."""
    return ProductShapeRules(
        rule_version="1.0.0",
        hubs_minimum=6,
        hubs_maximum=8,
        colour_variants_minimum=3,
        colour_variants_maximum=4,
        tags_count=13,
        images_count=10,
        video_count=1,
        description_sections_count=8,
        default_quantity=999,
    )


def create_fixture_product_spec(
    *,
    spec_id: UUID | None = None,
    workflow_id: UUID | None = None,
    product_id: UUID | None = None,
    identity: str = "Modern Digital Planner",
    base_category: str = "Planners & Organizers",
    buyer_problem: str = "Stay organized with a reusable digital planning system",
    title: str = "Ultimate 2027 Digital Planner Bundle",
    tier: str = "mass",
    real_price: float = 8.99,
    anchor_price: float = 14.99,
    hubs: tuple[str, ...] = (
        "Daily Planning",
        "Goal Tracking",
        "Habit Builder",
        "Budget Tracker",
        "Meal Planner",
        "Fitness Log",
    ),
    colour_variants: tuple[str, ...] = ("Sage Green", "Navy Blue", "Rose Gold"),
    features: tuple[str, ...] = (
        "Hyperlinked navigation",
        "Interactive checkboxes",
        "Monthly calendar views",
        "Weekly spread templates",
    ),
    lineage_kind: str = "ORIGINAL",
    parent_spec_id: UUID | None = None,
) -> ProductSpec:
    """Create a fixture ProductSpec for testing.

    Generates valid ProductSpec with reasonable defaults that pass validation.
    Supports ORIGINAL, RECONCEPT lineage kinds.

    Args:
        spec_id: Spec UUID (generates new if None)
        workflow_id: Workflow UUID (generates new if None)
        product_id: Product UUID (generates new if None)
        identity: Product identity niche
        base_category: Base category
        buyer_problem: Buyer problem statement
        title: Product title
        tier: mass or premium
        real_price: Real price
        anchor_price: Anchor price (must be >= real_price)
        hubs: Tuple of 6-8 unique hubs
        colour_variants: Tuple of 3-4 unique variants
        features: Tuple of features
        lineage_kind: ORIGINAL or RECONCEPT
        parent_spec_id: Parent spec UUID (required for RECONCEPT)

    Returns:
        Valid ProductSpec instance
    """
    if spec_id is None:
        spec_id = uuid4()
    if workflow_id is None:
        workflow_id = uuid4()
    if product_id is None:
        product_id = uuid4()

    # Generate concept fingerprint from identity + category + buyer_problem
    concept_parts = f"{identity}|{base_category}|{buyer_problem}"
    concept_fingerprint = sha256(concept_parts.encode()).hexdigest()

    # Evidence reference
    evidence = (
        EvidenceReference(
            evidence_id=spec_id,
            evidence_kind="FIXTURE_GENERATED",
            reference="tests/fixtures/products.py::create_fixture_product_spec",
        ),
    )

    return ProductSpec(
        spec_id=spec_id,
        workflow_id=workflow_id,
        product_id=product_id,
        version=1,
        lineage_kind=lineage_kind,  # type: ignore[arg-type]
        parent_spec_id=parent_spec_id,
        parent_product_id=None,
        parent_decision_id=None,
        parent_workflow_id=None,
        shape_rules=create_fixture_product_shape_rules(),
        identity=identity,
        base_category=base_category,
        buyer_problem=buyer_problem,
        title=title,
        tier=tier,
        real_price=real_price,
        anchor_price=anchor_price,
        currency="USD",
        hubs=hubs,
        colour_variants=colour_variants,
        features=features,
        experiment_plan="Test color variants and hub prominence on conversions",
        concept_fingerprint=concept_fingerprint,
        source_evidence=evidence,
        created_at=datetime.now(UTC),
    )


def create_fixture_teardown_report(
    *,
    report_id: UUID | None = None,
    workflow_id: UUID | None = None,
    competitor_reference: str = "https://www.etsy.com/listing/1234567890/competitor-digital-planner",
    structure_components: tuple[str, ...] = (
        "Main planner PDF (hyperlinked)",
        "12 monthly cover pages",
        "52 weekly spreads",
        "Daily planning pages (365)",
        "Goal setting worksheets (4)",
        "Habit tracker templates (3)",
        "Budget planning sheets (12)",
        "Quick reference guide PDF",
    ),
    buyer_journey: tuple[str, ...] = (
        "Product page with 10 lifestyle images + 1 demo video",
        "Purchase and instant download",
        "ZIP file with PDFs and installation guide",
        "Video tutorial link in welcome email",
    ),
    mechanics: tuple[str, ...] = (
        "PDF hyperlinks for navigation",
        "GoodNotes/Notability compatible layers",
        "Interactive checkboxes via form fields",
        "Text fields for goal entry",
    ),
) -> TeardownReport:
    """Create a fixture TeardownReport for testing (structure-only, no competitor IP).

    Generates valid TeardownReport with realistic structure observations
    but NO actual competitor content copying. Per Lane 4 scope: simulation only.

    Args:
        report_id: Report UUID (generates new if None)
        workflow_id: Workflow UUID (generates new if None)
        competitor_reference: Competitor product URL (fixture)
        structure_components: List of structural components observed
        buyer_journey: Buyer journey steps observed
        mechanics: Product mechanics/features observed

    Returns:
        Valid TeardownReport instance
    """
    if report_id is None:
        report_id = uuid4()
    if workflow_id is None:
        workflow_id = uuid4()

    # Evidence reference (fixture-generated, no real purchase)
    evidence = (
        EvidenceReference(
            evidence_id=report_id,
            evidence_kind="FIXTURE_TEARDOWN",
            reference="tests/fixtures/products.py::create_fixture_teardown_report (simulation)",
        ),
    )

    return TeardownReport(
        report_id=report_id,
        workflow_id=workflow_id,
        competitor_reference=competitor_reference,
        purchase_receipt_reference=None,  # No real purchase in fixture
        structure_components=structure_components,
        buyer_journey=buyer_journey,
        mechanics=mechanics,
        copied_protected_content=False,  # NEVER TRUE per D-0002, Lane 4 scope
        source_evidence=evidence,
        completed_at=datetime.now(UTC),
    )


def create_fixture_research_report(
    *,
    report_id: UUID | None = None,
    workflow_id: UUID | None = None,
    query_terms: tuple[str, ...] = ("digital planner", "printable planner", "GoodNotes planner"),
    observation_count: int = 30,
) -> ResearchReport:
    """Create a fixture ResearchReport for testing workflow linkage.

    Generates valid ResearchReport with realistic observations for 25-40 row grid.

    Args:
        report_id: Report UUID (generates new if None)
        workflow_id: Workflow UUID (generates new if None)
        query_terms: Search query terms used
        observation_count: Number of observations (25-40 per workbook)

    Returns:
        Valid ResearchReport instance
    """
    if report_id is None:
        report_id = uuid4()
    if workflow_id is None:
        workflow_id = uuid4()

    # Generate fixture observations
    observations: list[ResearchObservation] = []
    for i in range(observation_count):
        obs_id = uuid4()
        observations.append(
            ResearchObservation(
                observation_id=obs_id,
                source_reference=(
                    f"https://www.etsy.com/listing/{1234567890 + i}/fixture-listing-{i}"
                ),
                observed_at=datetime.now(UTC),
                title=f"Fixture Digital Planner {i + 1}",
                shop_reference=f"FixtureShop{i % 10}",
                facts={
                    "current_price": 7.99 + (i * 0.50),
                    "sales_count": 1000 + (i * 100),
                    "shop_age_years": 2 + (i % 5),
                    "badges": ["bestseller"] if i % 3 == 0 else [],
                },
                evidence=(
                    EvidenceReference(
                        evidence_id=obs_id,
                        evidence_kind="FIXTURE_RESEARCH",
                        reference=(
                            f"tests/fixtures/products.py::create_fixture_research_report obs {i}"
                        ),
                    ),
                ),
            )
        )

    return ResearchReport(
        report_id=report_id,
        workflow_id=workflow_id,
        source_policy_version="1.0.0-fixture",
        query_terms=query_terms,
        observations=tuple(observations),
        summary_facts={
            "total_observations": observation_count,
            "price_range": {"min": 7.99, "max": 7.99 + (observation_count * 0.50)},
            "young_fast_shops": observation_count // 3,
        },
        completed_at=datetime.now(UTC),
    )
