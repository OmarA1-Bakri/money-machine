"""Unit tests for A05 Product Strategy scorer — S05 L3.

Tests the four scoring dimensions and fail-closed threshold behavior:
- Score >= 30: QUALIFIED
- Score < 30: REJECTED
"""

from uuid import uuid4

import pytest

from money_machine.agents.contracts.product_strategy import ProductStrategyInput
from money_machine.agents.implementations.product_strategy import A05ProductStrategy
from money_machine.domain.enums import AgentRunStatus
from tests.fixtures.product_strategy_fixtures import (
    BACKUP_CANDIDATE,
    COMPLETE_SHORTLIST,
    QUALIFIED_CANDIDATE,
    REJECTED_CANDIDATE,
    THRESHOLD_CANDIDATE,
)


class TestA05ProductStrategyScoring:
    """Test the Low-Ticket scoring logic."""

    def test_qualified_candidate_passes_threshold(self):
        """Candidate with score >= 30 should be QUALIFIED."""
        agent = A05ProductStrategy()
        strategy_input = ProductStrategyInput(
            job_id=uuid4(),
            workflow_id=uuid4(),
            research_run_id=uuid4(),
            candidates=(QUALIFIED_CANDIDATE,),
            scoring_threshold=30,
            maximum_score=40,
        )

        result_dict = agent.execute(strategy_input.model_dump())

        assert result_dict["status"] == AgentRunStatus.SUCCESS
        assert result_dict["qualification_outcome"] == "QUALIFIED"
        assert result_dict["primary_candidate"]["total_score"] >= 30
        assert result_dict["primary_candidate"]["passed_threshold"] is True
        assert result_dict["primary_candidate"]["selection"] == "PRIMARY"
        assert result_dict["product_spec"] is not None

    def test_rejected_candidate_fails_threshold(self):
        """Candidate with score < 30 should be REJECTED."""
        agent = A05ProductStrategy()
        strategy_input = ProductStrategyInput(
            job_id=uuid4(),
            workflow_id=uuid4(),
            research_run_id=uuid4(),
            candidates=(REJECTED_CANDIDATE,),
            scoring_threshold=30,
            maximum_score=40,
        )

        result_dict = agent.execute(strategy_input.model_dump())

        assert result_dict["status"] == AgentRunStatus.SUCCESS
        assert result_dict["qualification_outcome"] == "REJECTED"
        assert result_dict["primary_candidate"]["total_score"] < 30
        assert result_dict["primary_candidate"]["passed_threshold"] is False
        assert result_dict["product_spec"] is None

    def test_primary_and_backup_selection(self):
        """Highest scoring is PRIMARY, second is BACKUP."""
        agent = A05ProductStrategy()
        strategy_input = ProductStrategyInput(
            job_id=uuid4(),
            workflow_id=uuid4(),
            research_run_id=uuid4(),
            candidates=(QUALIFIED_CANDIDATE, BACKUP_CANDIDATE),
            scoring_threshold=30,
            maximum_score=40,
        )

        result_dict = agent.execute(strategy_input.model_dump())

        assert result_dict["status"] == AgentRunStatus.SUCCESS
        assert result_dict["primary_candidate"]["rank"] == 1
        assert result_dict["primary_candidate"]["selection"] == "PRIMARY"
        assert result_dict["backup_candidate"] is not None
        assert result_dict["backup_candidate"]["rank"] == 2
        assert result_dict["backup_candidate"]["selection"] == "BACKUP"

    def test_no_backup_if_second_fails_threshold(self):
        """Backup is None if second candidate fails threshold."""
        agent = A05ProductStrategy()
        strategy_input = ProductStrategyInput(
            job_id=uuid4(),
            workflow_id=uuid4(),
            research_run_id=uuid4(),
            candidates=(QUALIFIED_CANDIDATE, REJECTED_CANDIDATE),
            scoring_threshold=30,
            maximum_score=40,
        )

        result_dict = agent.execute(strategy_input.model_dump())

        assert result_dict["status"] == AgentRunStatus.SUCCESS
        assert result_dict["primary_candidate"]["selection"] == "PRIMARY"
        assert result_dict["backup_candidate"] is None

    def test_complete_shortlist_ranking(self):
        """All five candidates are ranked correctly."""
        agent = A05ProductStrategy()
        strategy_input = ProductStrategyInput(
            job_id=uuid4(),
            workflow_id=uuid4(),
            research_run_id=uuid4(),
            candidates=COMPLETE_SHORTLIST,
            scoring_threshold=30,
            maximum_score=40,
        )

        result_dict = agent.execute(strategy_input.model_dump())

        assert result_dict["status"] == AgentRunStatus.SUCCESS
        assert len(result_dict["scored_candidates"]) == 5

        # Check ranking order
        scores = [c["total_score"] for c in result_dict["scored_candidates"]]
        assert scores == sorted(scores, reverse=True), "Candidates should be ranked by score"

        # Check ranks are sequential
        ranks = [c["rank"] for c in result_dict["scored_candidates"]]
        assert ranks == [1, 2, 3, 4, 5]

    def test_scoring_dimensions_present(self):
        """Each candidate has all four scoring dimensions."""
        agent = A05ProductStrategy()
        strategy_input = ProductStrategyInput(
            job_id=uuid4(),
            workflow_id=uuid4(),
            research_run_id=uuid4(),
            candidates=(QUALIFIED_CANDIDATE,),
            scoring_threshold=30,
            maximum_score=40,
        )

        result_dict = agent.execute(strategy_input.model_dump())

        primary = result_dict["primary_candidate"]
        assert len(primary["scoring"]) == 4

        dimensions = {s["dimension"] for s in primary["scoring"]}
        assert dimensions == {
            "impulse_priced",
            "tangible",
            "honest_promise",
            "trendy_but_tricky",
        }

        # Check total equals sum of dimensions
        total_from_dimensions = sum(s["score"] for s in primary["scoring"])
        assert primary["total_score"] == total_from_dimensions

    def test_evidence_collected(self):
        """Evidence is collected for scoring."""
        agent = A05ProductStrategy()
        strategy_input = ProductStrategyInput(
            job_id=uuid4(),
            workflow_id=uuid4(),
            research_run_id=uuid4(),
            candidates=(QUALIFIED_CANDIDATE,),
            scoring_threshold=30,
            maximum_score=40,
        )

        result_dict = agent.execute(strategy_input.model_dump())

        assert len(result_dict["evidence"]) >= 1
        assert all("evidence_type" in e for e in result_dict["evidence"])

    def test_product_spec_generated_when_qualified(self):
        """ProductSpec is generated only when primary passes threshold."""
        agent = A05ProductStrategy()
        strategy_input = ProductStrategyInput(
            job_id=uuid4(),
            workflow_id=uuid4(),
            research_run_id=uuid4(),
            candidates=(QUALIFIED_CANDIDATE,),
            scoring_threshold=30,
            maximum_score=40,
        )

        result_dict = agent.execute(strategy_input.model_dump())

        spec = result_dict["product_spec"]
        assert spec is not None
        assert spec["identity"] == QUALIFIED_CANDIDATE.identity
        assert spec["base_category"] == QUALIFIED_CANDIDATE.base_category
        assert len(spec["hubs"]) >= 6
        assert len(spec["hubs"]) <= 8
        assert len(spec["colour_variants"]) >= 3
        assert len(spec["colour_variants"]) <= 4
        assert spec["real_price"] <= spec["anchor_price"]

    def test_threshold_exact_boundary(self):
        """Test exact threshold boundary behavior."""
        agent = A05ProductStrategy()

        # Test score = 30 (should pass)
        strategy_input_30 = ProductStrategyInput(
            job_id=uuid4(),
            workflow_id=uuid4(),
            research_run_id=uuid4(),
            candidates=(THRESHOLD_CANDIDATE,),
            scoring_threshold=30,
            maximum_score=40,
        )

        result_30 = agent.execute(strategy_input_30.model_dump())

        # If score is exactly 30, it should qualify
        if result_30["primary_candidate"]["total_score"] == 30:
            assert result_30["qualification_outcome"] == "QUALIFIED"
            assert result_30["primary_candidate"]["passed_threshold"] is True

        # If score is 29, it should reject
        if result_30["primary_candidate"]["total_score"] == 29:
            assert result_30["qualification_outcome"] == "REJECTED"
            assert result_30["primary_candidate"]["passed_threshold"] is False

    def test_error_handling(self):
        """Test error handling with invalid input."""
        agent = A05ProductStrategy()

        # Missing required field
        invalid_input = {
            "job_id": str(uuid4()),
            "workflow_id": str(uuid4()),
            # Missing research_run_id and candidates
        }

        result_dict = agent.execute(invalid_input)

        assert result_dict["status"] == AgentRunStatus.FAILURE
        assert result_dict["error"] is not None
        assert result_dict["error"]["code"] == "PRODUCT_STRATEGY_FAILED"
        assert result_dict["qualification_outcome"] == "REJECTED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
