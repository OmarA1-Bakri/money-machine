from datetime import UTC, datetime
from pathlib import Path

import pytest

from money_machine.application.services.listing_service import ListingService
from money_machine.domain.models.asset import ArtifactReference
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import ProductFact, ProductSpec

SHA = "a" * 64
NOW = datetime(2026, 8, 9, tzinfo=UTC)


def spec() -> ProductSpec:
    return ProductSpec(
        product_spec_id="spec-1",
        candidate_id="candidate-1",
        identity_niche="adhd students",
        base_category="digital planner",
        target_buyer="People managing adhd students",
        promised_outcome="A structured digital planner workspace",
        hubs=("Home", "Courses", "Tasks", "Notes", "Reviews", "Archive"),
        colour_variants=("Ink", "Sand", "Sage"),
        features=("Linked course and task views",),
        product_facts=(
            ProductFact(
                claim="Configured with 6 hubs",
                category="HUB_INVENTORY",
                evidence_ids=("evidence-1",),
            ),
            ProductFact(
                claim="Includes Linked course and task views",
                category="FEATURE",
                evidence_ids=("evidence-1",),
            ),
            ProductFact(
                claim="Configured with 3 colour variants",
                category="COLOUR_VARIANTS",
                evidence_ids=("evidence-1",),
            ),
            ProductFact(
                claim="People managing adhd students",
                category="BUYER_FIT",
                evidence_ids=("evidence-1",),
            ),
            ProductFact(
                claim="A structured digital planner workspace",
                category="WORKFLOW_OUTCOME",
                evidence_ids=("evidence-1",),
            ),
        ),
        source_evidence_ids=("evidence-1",),
        spec_sha256=SHA,
    )


def build() -> BuildResult:
    artifact = ArtifactReference(
        artifact_id="artifact-1",
        relative_path=Path("products/spec-1/index.html"),
        media_type="text/html",
        byte_count=1,
        content_sha256=SHA,
    )
    return BuildResult(
        build_id="build-1",
        product_spec_id="spec-1",
        root_artifact_path="products/spec-1",
        artifacts=(artifact,),
        manifest_sha256=SHA,
        renderer_version="1",
    )


def qa(*, passed: bool = True) -> ProductQAResult:
    return ProductQAResult(
        qa_result_id="qa-1",
        build_id="build-1",
        passed=passed,
        findings=() if passed else ("broken build",),
        checked_at=NOW,
        result_sha256=SHA,
    )


def test_merchandising_is_product_specific_complete_and_replay_stable() -> None:
    service = ListingService()

    first = service.create(spec(), build(), qa())
    second = service.create(spec(), build(), qa())

    assert first == second
    assert first.title.startswith("ADHD Students")
    assert len(first.title) <= 140
    assert len(first.tags) == len(set(first.tags)) == 13
    assert all(1 <= len(tag) <= 20 for tag in first.tags)
    assert first.description.count("## ") == 8
    assert "Configured with 6 hubs" in first.description
    assert "placeholder" not in first.description.casefold()
    assert "sales" not in first.description.casefold()
    assert first.preview_video_status == "NOT_GENERATED"
    assert len(first.package_sha256) == 64


def test_merchandising_rejects_failed_or_mismatched_qa() -> None:
    service = ListingService()

    with pytest.raises(ValueError, match="QA must pass"):
        service.create(spec(), build(), qa(passed=False))
    with pytest.raises(ValueError, match="build"):
        service.create(spec(), build(), qa().model_copy(update={"build_id": "other"}))


def test_merchandising_uses_only_current_product_and_whole_word_tags() -> None:
    yoga = spec().model_copy(
        update={
            "identity_niche": "yoga teachers",
            "base_category": "meal planner",
            "target_buyer": "People managing yoga teachers",
            "promised_outcome": "A structured meal planner workspace",
            "hubs": ("Home", "Week", "Recipes", "Groceries", "Prep", "Archive"),
            "colour_variants": ("Clay", "Moss", "Cream"),
            "features": ("Weekly meal and grocery views",),
            "product_facts": (
                ProductFact(
                    claim="Configured with 6 hubs",
                    category="HUB_INVENTORY",
                    evidence_ids=("evidence-1",),
                ),
                ProductFact(
                    claim="Includes Weekly meal and grocery views",
                    category="FEATURE",
                    evidence_ids=("evidence-1",),
                ),
                ProductFact(
                    claim="Configured with 3 colour variants",
                    category="COLOUR_VARIANTS",
                    evidence_ids=("evidence-1",),
                ),
                ProductFact(
                    claim="People managing yoga teachers",
                    category="BUYER_FIT",
                    evidence_ids=("evidence-1",),
                ),
                ProductFact(
                    claim="A structured meal planner workspace",
                    category="WORKFLOW_OUTCOME",
                    evidence_ids=("evidence-1",),
                ),
            ),
        }
    )
    package = ListingService().create(yoga, build(), qa())

    rendered = f"{package.title} {' '.join(package.tags)} {package.description}".casefold()
    assert "student" not in rendered
    assert "coursework" not in rendered
    assert "academic" not in rendered
    assert package.title == "Yoga Teachers Meal Planner"
    assert all(not tag.endswith((" planne", " templat")) for tag in package.tags)
    assert package.description.startswith("## Overview\n")


@pytest.mark.parametrize(
    "update",
    (
        {"promised_outcome": "Cures ADHD permanently"},
        {"target_buyer": "Guaranteed high-income customers"},
    ),
)
def test_merchandising_rejects_promised_outcome_absent_and_buyer_copy(
    update: dict[str, str],
) -> None:
    unsupported = spec().model_copy(update=update)

    with pytest.raises(ValueError, match="product fact"):
        ListingService().create(unsupported, build(), qa())


@pytest.mark.parametrize(
    ("field", "claim"),
    (
        ("promised_outcome", "Track guaranteed profits"),
        ("promised_outcome", "Manage passive income"),
        ("promised_outcome", "Access recurring revenue"),
        ("target_buyer", "Creators planning guaranteed profits"),
    ),
)
def test_listing_path_rejects_regex_shaped_commercial_claims(
    field: str,
    claim: str,
) -> None:
    original = spec()
    replaced = original.promised_outcome if field == "promised_outcome" else original.target_buyer
    unsupported = original.model_copy(
        update={
            field: claim,
            "product_facts": tuple(
                fact.model_copy(update={"claim": claim}) if fact.claim == replaced else fact
                for fact in original.product_facts
            ),
        }
    )

    with pytest.raises(ValueError, match="product fact"):
        ListingService().create(unsupported, build(), qa())
