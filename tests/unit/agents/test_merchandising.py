from datetime import UTC, datetime
from pathlib import Path

import pytest

from money_machine.application.services.listing_service import ListingService
from money_machine.domain.models.asset import ArtifactReference
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import ProductSpec

SHA = "a" * 64
NOW = datetime(2026, 8, 9, tzinfo=UTC)


def spec() -> ProductSpec:
    return ProductSpec(
        product_spec_id="spec-1",
        candidate_id="candidate-1",
        identity_niche="adhd students",
        base_category="digital planner",
        target_buyer="Students who need a low-friction planning system",
        promised_outcome="Organize coursework in one consistent workspace",
        hubs=("Home", "Courses", "Tasks", "Notes", "Reviews", "Archive"),
        colour_variants=("Ink", "Sand", "Sage"),
        features=("Linked course and task views",),
        product_facts=(
            "Includes six navigation hubs",
            "Includes linked course and task views",
            "Available in ink, sand, and sage colour variants",
            "Students who need a low-friction planning system",
            "Organize coursework in one consistent workspace",
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
    assert "Includes six navigation hubs" in first.description
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
            "target_buyer": "Yoga teachers planning balanced weekly meals",
            "promised_outcome": "Plan balanced meals in one calm workspace",
            "hubs": ("Home", "Week", "Recipes", "Groceries", "Prep", "Archive"),
            "colour_variants": ("Clay", "Moss", "Cream"),
            "features": ("Weekly meal and grocery views",),
            "product_facts": (
                "Includes six navigation hubs",
                "Includes weekly meal and grocery views",
                "Available in clay, moss, and cream colour variants",
                "Yoga teachers planning balanced weekly meals",
                "Plan balanced meals in one calm workspace",
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
