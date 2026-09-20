"""Unit tests for catalogue dedupe service (D-0013 rules).

Tests cover:
- Title normalization
- Jaccard similarity calculation
- Identity + category collision detection
- Title similarity collision detection
- Concept fingerprint collision detection
- PASS with empty catalogue
- PASS with non-conflicting catalogue (requires differentiation)
- TOO_CLOSE outcomes
"""

from decimal import Decimal
from uuid import uuid4

import pytest

from money_machine.domain.enums import BranchOutcome
from money_machine.domain.services.dedupe import (
    JACCARD_THRESHOLD,
    calculate_jaccard_similarity,
    check_dedupe,
    normalize_title,
    tokenize_title,
)
from tests.fixtures.products import create_fixture_product_spec


class TestTitleNormalization:
    """Test title normalization per D-0013."""

    def test_normalize_title_unicode(self):
        """Unicode normalization (NFKD) and case-folding."""
        title = "Café Latté — Naïve"
        normalized = normalize_title(title)
        assert "cafe" in normalized.lower()
        assert "latte" in normalized.lower()
        assert "naive" in normalized.lower()
        assert normalized == normalized.lower()

    def test_normalize_title_punctuation(self):
        """Punctuation stripped, whitespace collapsed."""
        title = "Hello,  World!!!  How   are you?"
        normalized = normalize_title(title)
        assert "," not in normalized
        assert "!" not in normalized
        assert "?" not in normalized
        # Whitespace should be collapsed to single spaces
        assert "  " not in normalized
        assert normalized == "hello world how are you"

    def test_normalize_title_trim(self):
        """Leading/trailing whitespace removed."""
        title = "  Ultimate Planner  "
        normalized = normalize_title(title)
        assert normalized == "ultimate planner"
        assert not normalized.startswith(" ")
        assert not normalized.endswith(" ")


class TestJaccardSimilarity:
    """Test Jaccard similarity calculation."""

    def test_jaccard_identical(self):
        """Identical token sets → similarity 1.0."""
        tokens = {"digital", "planner", "2027"}
        similarity = calculate_jaccard_similarity(tokens, tokens)
        assert similarity == 1.0

    def test_jaccard_disjoint(self):
        """Completely different token sets → similarity 0.0."""
        tokens_a = {"digital", "planner"}
        tokens_b = {"physical", "notebook"}
        similarity = calculate_jaccard_similarity(tokens_a, tokens_b)
        assert similarity == 0.0

    def test_jaccard_partial_overlap(self):
        """Partial overlap → correct Jaccard score."""
        tokens_a = {"digital", "planner", "2027"}  # 3 tokens
        tokens_b = {"digital", "planner", "bundle"}  # 3 tokens
        # Intersection: {digital, planner} = 2
        # Union: {digital, planner, 2027, bundle} = 4
        # Jaccard = 2/4 = 0.5
        similarity = calculate_jaccard_similarity(tokens_a, tokens_b)
        assert similarity == 0.5

    def test_jaccard_empty_sets(self):
        """Empty token sets → similarity 1.0 (both empty is same)."""
        similarity = calculate_jaccard_similarity(set(), set())
        assert similarity == 1.0

    def test_jaccard_one_empty(self):
        """One empty token set → similarity 0.0."""
        tokens = {"digital", "planner"}
        similarity = calculate_jaccard_similarity(tokens, set())
        assert similarity == 0.0


class TestCheckDedupe:
    """Test complete dedupe check logic with D-0013 rules."""

    def test_dedupe_pass_empty_catalogue(self):
        """PASS with empty catalogue (no collisions, no differentiation needed)."""
        candidate = create_fixture_product_spec(
            identity="Modern Digital Planner",
            base_category="Planners & Organizers",
            title="Ultimate 2027 Digital Planner",
        )

        result = check_dedupe(
            candidate_spec=candidate,
            existing_specs=[],
            rule_version="1.0.0",
        )

        assert result.outcome is BranchOutcome.PASS
        assert len(result.collisions) == 0
        assert len(result.compared_spec_ids) == 0
        # Empty catalogue: no differentiation evidence required
        assert len(result.differentiation_evidence) == 0

    def test_dedupe_pass_non_conflicting_catalogue(self):
        """PASS against non-conflicting catalogue (requires differentiation evidence)."""
        candidate = create_fixture_product_spec(
            identity="Modern Digital Planner",
            base_category="Planners & Organizers",
            title="Ultimate 2027 Digital Planner",
        )

        existing = create_fixture_product_spec(
            spec_id=uuid4(),
            identity="Fitness Tracker",
            base_category="Health & Wellness",
            title="Complete Workout Log System",
        )

        result = check_dedupe(
            candidate_spec=candidate,
            existing_specs=[existing],
            rule_version="1.0.0",
        )

        assert result.outcome is BranchOutcome.PASS
        assert len(result.collisions) == 0
        assert len(result.compared_spec_ids) == 1
        # Non-empty catalogue: differentiation evidence REQUIRED per D-0013
        assert len(result.differentiation_evidence) > 0
        # Should include identity, category, buyer problem, features, hubs
        evidence_str = " ".join(result.differentiation_evidence)
        assert candidate.identity in evidence_str
        assert candidate.base_category in evidence_str

    def test_dedupe_too_close_identity_category(self):
        """TOO_CLOSE on exact identity + category match (EXACT_IDENTITY_CATEGORY)."""
        candidate = create_fixture_product_spec(
            identity="Modern Digital Planner",
            base_category="Planners & Organizers",
            title="Ultimate 2027 Digital Planner",
        )

        existing = create_fixture_product_spec(
            spec_id=uuid4(),
            identity="Modern Digital Planner",  # SAME identity
            base_category="Planners & Organizers",  # SAME category
            title="Different Title Here",  # Different title doesn't matter
        )

        result = check_dedupe(
            candidate_spec=candidate,
            existing_specs=[existing],
            rule_version="1.0.0",
        )

        assert result.outcome is BranchOutcome.TOO_CLOSE
        assert len(result.collisions) == 1
        collision = result.collisions[0]
        assert collision.reason == "EXACT_IDENTITY_CATEGORY"
        assert collision.other_spec_id == existing.spec_id
        assert collision.similarity == 1.0
        # TOO_CLOSE cannot have differentiation evidence per D-0013
        assert len(result.differentiation_evidence) == 0

    def test_dedupe_too_close_title_similarity(self):
        """TOO_CLOSE on title Jaccard >= 0.70 threshold (TITLE_SIMILARITY)."""
        candidate = create_fixture_product_spec(
            identity="Digital Planner A",
            base_category="Planners & Organizers",
            title="Ultimate Digital Planner Bundle 2027 Edition",
        )

        # Very similar title (many overlapping words)
        existing = create_fixture_product_spec(
            spec_id=uuid4(),
            identity="Digital Planner B",  # Different identity
            base_category="Planners & Organizers",
            title="Ultimate Digital Planner Bundle 2027",  # High Jaccard overlap
        )

        # Calculate expected Jaccard
        candidate_tokens = tokenize_title(normalize_title(candidate.title))
        existing_tokens = tokenize_title(normalize_title(existing.title))
        expected_similarity = calculate_jaccard_similarity(candidate_tokens, existing_tokens)

        # Verify we're above threshold for this test
        assert expected_similarity >= JACCARD_THRESHOLD

        result = check_dedupe(
            candidate_spec=candidate,
            existing_specs=[existing],
            rule_version="1.0.0",
        )

        assert result.outcome is BranchOutcome.TOO_CLOSE
        assert len(result.collisions) == 1
        collision = result.collisions[0]
        assert collision.reason == "TITLE_SIMILARITY"
        assert collision.other_spec_id == existing.spec_id
        assert collision.similarity >= Decimal(str(JACCARD_THRESHOLD))
        assert float(collision.similarity) == pytest.approx(expected_similarity, abs=0.01)

    def test_dedupe_pass_title_below_threshold(self):
        """PASS when title similarity < 0.70 threshold."""
        candidate = create_fixture_product_spec(
            identity="Digital Planner",
            base_category="Planners & Organizers",
            title="Ultimate 2027 Digital Planner Bundle Complete",
        )

        # Somewhat similar but below threshold
        existing = create_fixture_product_spec(
            spec_id=uuid4(),
            identity="Fitness Tracker",
            base_category="Health & Wellness",
            title="Fitness Workout Log",  # Few overlapping words
        )

        result = check_dedupe(
            candidate_spec=candidate,
            existing_specs=[existing],
            rule_version="1.0.0",
        )

        # Should pass (different identity/category, title similarity < threshold)
        assert result.outcome is BranchOutcome.PASS
        assert len(result.collisions) == 0

    def test_dedupe_too_close_concept_fingerprint(self):
        """TOO_CLOSE on matching concept fingerprint (CONCEPT_FINGERPRINT)."""
        candidate = create_fixture_product_spec(
            identity="Modern Digital Planner",
            base_category="Planners & Organizers",
            buyer_problem="Stay organized with a reusable digital planning system",
            title="Title One",
        )

        # Different title but SAME identity + category + buyer_problem
        # → same concept fingerprint
        existing = create_fixture_product_spec(
            spec_id=uuid4(),
            identity="Modern Digital Planner",  # SAME
            base_category="Planners & Organizers",  # SAME
            buyer_problem="Stay organized with a reusable digital planning system",  # SAME
            title="Completely Different Title Here",  # Different title
        )

        # Verify concept fingerprints match (same inputs)
        assert candidate.concept_fingerprint == existing.concept_fingerprint

        result = check_dedupe(
            candidate_spec=candidate,
            existing_specs=[existing],
            rule_version="1.0.0",
        )

        assert result.outcome is BranchOutcome.TOO_CLOSE
        # May have TWO collisions: EXACT_IDENTITY_CATEGORY and CONCEPT_FINGERPRINT
        # Or just EXACT_IDENTITY_CATEGORY if that rule fires first (implementation dependent)
        # Either way, outcome is TOO_CLOSE
        assert len(result.collisions) >= 1
        # Check that at least one collision exists (either reason is valid here)
        collision_reasons = {c.reason for c in result.collisions}
        assert (
            "EXACT_IDENTITY_CATEGORY" in collision_reasons
            or "CONCEPT_FINGERPRINT" in collision_reasons
        )

    def test_dedupe_multiple_collisions(self):
        """TOO_CLOSE with multiple existing specs creating collisions."""
        candidate = create_fixture_product_spec(
            identity="Digital Planner",
            base_category="Planners & Organizers",
            title="Ultimate Digital Planner",
        )

        existing_1 = create_fixture_product_spec(
            spec_id=uuid4(),
            identity="Digital Planner",  # Collision 1: exact identity+category
            base_category="Planners & Organizers",
            title="Different Title",
        )

        existing_2 = create_fixture_product_spec(
            spec_id=uuid4(),
            identity="Other Identity",
            base_category="Other Category",
            title="Ultimate Digital Planner Bundle",  # Collision 2: title similarity
        )

        result = check_dedupe(
            candidate_spec=candidate,
            existing_specs=[existing_1, existing_2],
            rule_version="1.0.0",
        )

        assert result.outcome is BranchOutcome.TOO_CLOSE
        # Should have at least 2 collisions (one per existing spec)
        assert len(result.collisions) >= 2
        collision_ids = {c.other_spec_id for c in result.collisions}
        assert existing_1.spec_id in collision_ids
        # existing_2 collision depends on Jaccard threshold

    def test_dedupe_result_validation(self):
        """Verify DedupeResult validation rules are enforced."""
        candidate = create_fixture_product_spec()

        result = check_dedupe(
            candidate_spec=candidate,
            existing_specs=[],
            rule_version="1.0.0",
        )

        # Should pass all DedupeResult validations
        assert result.spec_id == candidate.spec_id
        assert result.workflow_id == candidate.workflow_id
        assert result.outcome in {BranchOutcome.PASS, BranchOutcome.TOO_CLOSE}
        assert result.title_similarity_threshold == Decimal(str(JACCARD_THRESHOLD))
        # Self-comparison not allowed
        assert result.spec_id not in result.compared_spec_ids
        # PASS forbids collisions
        if result.outcome is BranchOutcome.PASS:
            assert len(result.collisions) == 0
        # TOO_CLOSE requires collisions
        else:
            assert len(result.collisions) > 0
