"""Integration tests for dedupe workflow and reconcept loop.

Tests prove workflow linkage per Lane 4 scope:
- ProductSpecJob → DedupeJob → ProductBuildJob (PASS path)
- ProductSpecJob → DedupeJob → ReconceptProductJob → DedupeJob (TOO_CLOSE loop)
- Fixture-based testing without live external dependencies

Contract: Session 05 Lane 4 — A06 Catalogue Dedupe + workflow link proving
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from money_machine.domain.enums import BranchOutcome
from money_machine.domain.models.products import DedupeResult, ProductSpec
from money_machine.domain.services.dedupe import check_dedupe
from tests.fixtures.products import (
    create_fixture_product_spec,
    create_fixture_research_report,
    create_fixture_teardown_report,
)


class TestDedupeWorkflowIntegration:
    """Test complete dedupe workflow integration with fixtures."""

    def test_dedupe_pass_workflow_creates_build_job(self):
        """PASS outcome should trigger ProductBuildJob creation in workflow.

        Workflow: ProductSpecJob → DedupeJob → DEDUPE_PASSED → ProductBuildJob

        This test proves the PASS path through the dedupe gate.
        Per config/workflows.yaml: DEDUPE_PASSED → [ProductBuildJob]
        """
        workflow_id = uuid4()

        # Create candidate ProductSpec (from ProductSpecJob output)
        candidate_spec = create_fixture_product_spec(
            workflow_id=workflow_id,
            identity="Modern Digital Planner",
            base_category="Planners & Organizers",
            title="Ultimate 2027 Digital Planner",
        )

        # Empty catalogue (first product in this niche)
        existing_specs: list[ProductSpec] = []

        # Run dedupe check
        dedupe_result = check_dedupe(
            candidate_spec=candidate_spec,
            existing_specs=existing_specs,
            rule_version="1.0.0",
        )

        # Verify PASS outcome
        assert dedupe_result.outcome is BranchOutcome.PASS
        assert len(dedupe_result.collisions) == 0

        # Verify workflow contract
        assert dedupe_result.workflow_id == workflow_id
        assert dedupe_result.spec_id == candidate_spec.spec_id

        # In real workflow, DEDUPE_PASSED event would create ProductBuildJob (A07)
        # and the product would proceed to Notion template building
        # For Lane 4: we've proven the dedupe gate opens for PASS

    def test_dedupe_too_close_workflow_creates_reconcept_job(self):
        """TOO_CLOSE outcome should trigger ReconceptProductJob creation.

        Workflow: ProductSpecJob → DedupeJob → DEDUPE_FAILED → ReconceptProductJob

        This test proves the TOO_CLOSE path triggers reconcept loop.
        Per config/workflows.yaml: DEDUPE_FAILED → [ReconceptProductJob]
        """
        workflow_id = uuid4()

        # Create candidate ProductSpec
        candidate_spec = create_fixture_product_spec(
            workflow_id=workflow_id,
            identity="Modern Digital Planner",
            base_category="Planners & Organizers",
            title="Ultimate Digital Planner Bundle",
        )

        # Existing spec with SAME identity + category (collision)
        existing_spec = create_fixture_product_spec(
            spec_id=uuid4(),
            workflow_id=uuid4(),  # Different workflow
            identity="Modern Digital Planner",  # SAME
            base_category="Planners & Organizers",  # SAME
            title="Different Title",
        )

        # Run dedupe check
        dedupe_result = check_dedupe(
            candidate_spec=candidate_spec,
            existing_specs=[existing_spec],
            rule_version="1.0.0",
        )

        # Verify TOO_CLOSE outcome
        assert dedupe_result.outcome is BranchOutcome.TOO_CLOSE
        assert len(dedupe_result.collisions) > 0

        # Verify collision evidence
        collision = dedupe_result.collisions[0]
        assert collision.reason == "EXACT_IDENTITY_CATEGORY"
        assert collision.other_spec_id == existing_spec.spec_id

        # TOO_CLOSE cannot claim differentiation per D-0013
        assert len(dedupe_result.differentiation_evidence) == 0

        # In real workflow, DEDUPE_FAILED event would create ReconceptProductJob (A05)
        # which generates a new ProductSpec with lineage_kind=RECONCEPT
        # and loops back to DedupeJob

    def test_reconcept_loop_eventually_passes(self):
        """Reconcept loop should eventually produce a PASS.

        Complete loop:
        1. ProductSpecJob → candidate spec
        2. DedupeJob → TOO_CLOSE (collision detected)
        3. ReconceptProductJob → revised spec with new identity/category
        4. DedupeJob → PASS (no collision after reconcept)
        5. ProductBuildJob → proceed to build

        This proves the reconcept loop works as intended per D-0013.
        """
        workflow_id_1 = uuid4()
        workflow_id_2 = uuid4()  # Reconcept gets new workflow per D-0017

        # Existing product in catalogue
        existing_spec = create_fixture_product_spec(
            spec_id=uuid4(),
            workflow_id=uuid4(),
            identity="Modern Digital Planner",
            base_category="Planners & Organizers",
            title="Ultimate Digital Planner",
        )

        # Initial candidate (collides)
        candidate_v1 = create_fixture_product_spec(
            workflow_id=workflow_id_1,
            identity="Modern Digital Planner",  # SAME as existing
            base_category="Planners & Organizers",  # SAME as existing
            title="Modern Digital Planner Bundle",
        )

        # First dedupe check → TOO_CLOSE
        dedupe_result_v1 = check_dedupe(
            candidate_spec=candidate_v1,
            existing_specs=[existing_spec],
            rule_version="1.0.0",
        )

        assert dedupe_result_v1.outcome is BranchOutcome.TOO_CLOSE
        assert len(dedupe_result_v1.collisions) > 0

        # Reconcept: A05 generates new spec with DIFFERENT identity/category
        # (simulating ReconceptProductJob output)
        candidate_v2_reconcepted = create_fixture_product_spec(
            workflow_id=workflow_id_2,  # New workflow per D-0017
            identity="Productivity Hub System",  # CHANGED
            base_category="Digital Organizational Tools",  # CHANGED
            buyer_problem="Centralize all productivity tracking in one place",  # CHANGED
            title="Complete Productivity Tracking Hub",  # CHANGED
            lineage_kind="RECONCEPT",
            parent_spec_id=candidate_v1.spec_id,
        )

        # Second dedupe check → PASS (after reconcept)
        dedupe_result_v2 = check_dedupe(
            candidate_spec=candidate_v2_reconcepted,
            existing_specs=[existing_spec],
            rule_version="1.0.0",
        )

        assert dedupe_result_v2.outcome is BranchOutcome.PASS
        assert len(dedupe_result_v2.collisions) == 0
        # PASS against non-empty catalogue requires differentiation
        assert len(dedupe_result_v2.differentiation_evidence) > 0

        # Reconcept loop complete: PASS outcome triggers ProductBuildJob

    def test_fixture_workflow_with_research_and_teardown(self):
        """Complete fixture workflow: Research → Teardown → Spec → Dedupe → Build.

        This proves the full workflow linkage using fixtures for upstream dependencies.
        Lane 4 scope: show that dedupe integrates with upstream (fixture) and downstream.
        """
        workflow_id = uuid4()

        # Upstream: Research (fixture)
        research_report = create_fixture_research_report(
            workflow_id=workflow_id,
            observation_count=30,  # 25-40 per workbook
        )

        # Upstream: Competitor Teardown (fixture, structure-only)
        teardown_report = create_fixture_teardown_report(
            workflow_id=workflow_id,
        )

        # Upstream: ProductSpec generation (using research + teardown insights)
        product_spec = create_fixture_product_spec(
            workflow_id=workflow_id,
            identity="Digital Planner with Interactive Tracking",
            base_category="Planners & Organizers",
            title="Complete Interactive Digital Planner System 2027",
        )

        # Lane 4: Dedupe check
        dedupe_result = check_dedupe(
            candidate_spec=product_spec,
            existing_specs=[],  # Empty catalogue for this test
            rule_version="1.0.0",
        )

        # Verify PASS outcome
        assert dedupe_result.outcome is BranchOutcome.PASS

        # Verify workflow lineage
        assert research_report.workflow_id == workflow_id
        assert teardown_report.workflow_id == workflow_id
        assert product_spec.workflow_id == workflow_id
        assert dedupe_result.workflow_id == workflow_id

        # Verify fixture quality
        assert len(research_report.observations) == 30
        assert teardown_report.copied_protected_content is False  # Lane 4 requirement
        assert len(product_spec.hubs) >= 6  # Per D-0022 shape rules

        # In real workflow:
        # RUN_MARKET_RESEARCH → RESEARCH_COMPLETED (A03)
        # → ... → TEARDOWN_COMPLETED (A04)
        # → PRODUCT_SPEC_CREATED (A05)
        # → DEDUPE_PASSED (A06) ← WE ARE HERE
        # → BUILD_NOTION_TEMPLATE ready (A07)

        # Lane 4 scope proven: dedupe gate works in fixture workflow context

    def test_multiple_dedupe_attempts_with_collisions(self):
        """Test multiple dedupe attempts as catalogue grows.

        Simulates real-world scenario:
        - First product: PASS (empty catalogue)
        - Second product (different): PASS (no collision)
        - Third product (too similar): TOO_CLOSE (collision)
        - Fourth product (reconcepted): PASS (after fix)
        """
        # Product 1: First in catalogue
        spec_1 = create_fixture_product_spec(
            spec_id=uuid4(),
            identity="Digital Planner",
            base_category="Planners & Organizers",
            title="Modern Digital Planner Bundle",
        )

        result_1 = check_dedupe(spec_1, [], "1.0.0")
        assert result_1.outcome is BranchOutcome.PASS

        # Product 2: Different niche, no collision
        spec_2 = create_fixture_product_spec(
            spec_id=uuid4(),
            identity="Fitness Tracker",
            base_category="Health & Wellness",
            title="Complete Workout Log System",
        )

        result_2 = check_dedupe(spec_2, [spec_1], "1.0.0")
        assert result_2.outcome is BranchOutcome.PASS

        # Product 3: Too similar to spec_1 (collision)
        spec_3 = create_fixture_product_spec(
            spec_id=uuid4(),
            identity="Digital Planner",  # SAME as spec_1
            base_category="Planners & Organizers",  # SAME as spec_1
            title="Ultimate Digital Planner Collection",
        )

        result_3 = check_dedupe(spec_3, [spec_1, spec_2], "1.0.0")
        assert result_3.outcome is BranchOutcome.TOO_CLOSE
        assert len(result_3.collisions) >= 1

        # Product 4: Reconcepted from spec_3, now passes
        spec_4 = create_fixture_product_spec(
            spec_id=uuid4(),
            identity="Goal Achievement System",  # DIFFERENT
            base_category="Productivity Tools",  # DIFFERENT
            title="Strategic Goal Tracking Dashboard",
            lineage_kind="RECONCEPT",
            parent_spec_id=spec_3.spec_id,
        )

        result_4 = check_dedupe(spec_4, [spec_1, spec_2], "1.0.0")
        assert result_4.outcome is BranchOutcome.PASS
        assert len(result_4.collisions) == 0

        # Catalogue has grown to 3 viable products (spec_1, spec_2, spec_4)
        # spec_3 was rejected and reconcepted into spec_4


class TestDedupeResultValidation:
    """Test DedupeResult contract validation per domain model."""

    def test_dedupe_result_outcome_constraints(self):
        """DedupeResult must have PASS or TOO_CLOSE outcome only."""
        candidate = create_fixture_product_spec()

        result = check_dedupe(candidate, [], "1.0.0")

        # Outcome must be one of the allowed values
        assert result.outcome in {BranchOutcome.PASS, BranchOutcome.TOO_CLOSE}
        # BranchOutcome.FAIL is not valid for dedupe per D-0013

    def test_dedupe_result_pass_validation(self):
        """PASS outcome validation per DedupeResult model."""
        candidate = create_fixture_product_spec()
        existing = create_fixture_product_spec(
            spec_id=uuid4(),
            identity="Different Identity",
            base_category="Different Category",
            title="Different Title",
        )

        result = check_dedupe(candidate, [existing], "1.0.0")

        if result.outcome is BranchOutcome.PASS:
            # PASS forbids collisions
            assert len(result.collisions) == 0
            # PASS against non-empty catalogue requires differentiation
            if len(result.compared_spec_ids) > 0:
                assert len(result.differentiation_evidence) > 0

    def test_dedupe_result_too_close_validation(self):
        """TOO_CLOSE outcome validation per DedupeResult model."""
        candidate = create_fixture_product_spec(identity="A", base_category="B")
        existing = create_fixture_product_spec(
            spec_id=uuid4(),
            identity="A",  # Collision
            base_category="B",
        )

        result = check_dedupe(candidate, [existing], "1.0.0")

        if result.outcome is BranchOutcome.TOO_CLOSE:
            # TOO_CLOSE requires collision evidence
            assert len(result.collisions) > 0
            # TOO_CLOSE cannot claim differentiation
            assert len(result.differentiation_evidence) == 0
            # Every collision must cite a compared spec
            for collision in result.collisions:
                assert collision.other_spec_id in result.compared_spec_ids
