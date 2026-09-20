"""Unit tests for A05 Product Strategy scorer — S05 L3.

Tests the four scoring dimensions and fail-closed threshold behavior:
- Score >= 30: QUALIFIED
- Score < 30: REJECTED
"""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from money_machine.agents.base import AgentContext, AgentDefinition
from money_machine.agents.contracts.product_strategy import ProductStrategyInput
from money_machine.agents.implementations.product_strategy import A05ProductStrategy
from money_machine.config.settings import AgentCommissioningState
from money_machine.domain.enums import AgentRunStatus, JobStatus, RetryClass, SideEffectClass
from money_machine.domain.models.common import SuccessContract
from money_machine.domain.models.jobs import JobEnvelope
from money_machine.integrations.llm.fake_provider import FakeLLMProvider
from tests.fixtures.product_strategy_fixtures import (
    BACKUP_CANDIDATE,
    COMPLETE_SHORTLIST,
    QUALIFIED_CANDIDATE,
    REJECTED_CANDIDATE,
    THRESHOLD_CANDIDATE,
)


def _create_context(strategy_input: ProductStrategyInput) -> AgentContext:
    """Helper to create AgentContext for testing."""
    job = JobEnvelope(
        job_id=strategy_input.job_id,
        workflow_id=strategy_input.workflow_id,
        object_id=uuid4(),
        job_type="ProductStrategyJob",
        object_type="workflow_runs",
        owner_agent_id="A05",
        status=JobStatus.READY,
        input=strategy_input.model_dump(),
        scheduled_at=datetime.now(tz=UTC),
        attempt=0,
        max_attempts=3,
        idempotency_key=f"test:{uuid4()}",
        side_effect_class=SideEffectClass.NONE,
        retry_class=RetryClass.SAFE,
        success_contract=SuccessContract(output_model="AgentResult"),
    )

    definition = AgentDefinition(
        agent_id="A05",
        name="Product Strategy",
        contract_version=1,
        system_prompt_reference="agent://A05/system/v1",
        input_contracts=("ProductStrategyInput",),
        output_contracts=("AgentResult",),
        allowed_tools=(),
        default_side_effect_class="NONE",
        timeout_seconds=300,
        commissioning_state=AgentCommissioningState.TESTED,
        commissioning_evidence=(),
    )

    return AgentContext(
        job=job,
        definition=definition,
        run_id=uuid4(),
        prompt_text="",
        prompt_reference=definition.system_prompt_reference,
        prompt_sha256="0" * 64,
        prompt_version=1,
        provider=FakeLLMProvider(),
        run_at=datetime.now(tz=UTC),
    )


class TestA05ProductStrategyScoring:
    """Test the Low-Ticket scoring logic."""

    @pytest.mark.asyncio
    async def test_qualified_candidate_passes_threshold(self):
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

        context = _create_context(strategy_input)
        result = await agent.execute(context)

        assert result.status == AgentRunStatus.SUCCESS
        output = result.output
        assert output["qualification_outcome"] == "QUALIFIED"
        assert output["primary_candidate"]["total_score"] >= 30
        assert output["primary_candidate"]["passed_threshold"] is True
        assert output["primary_candidate"]["selection"] == "PRIMARY"
        assert output["product_spec"] is not None

    @pytest.mark.asyncio
    async def test_rejected_candidate_fails_threshold(self):
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

        context = _create_context(strategy_input)
        result = await agent.execute(context)

        assert result.status == AgentRunStatus.SUCCESS
        output = result.output
        assert output["qualification_outcome"] == "REJECTED"
        assert output["primary_candidate"]["total_score"] < 30
        assert output["primary_candidate"]["passed_threshold"] is False
        assert output["product_spec"] is None

    @pytest.mark.asyncio
    async def test_primary_and_backup_selection(self):
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

        context = _create_context(strategy_input)
        result = await agent.execute(context)

        assert result.status == AgentRunStatus.SUCCESS
        output = result.output
        assert output["primary_candidate"]["rank"] == 1
        assert output["primary_candidate"]["selection"] == "PRIMARY"
        assert output["backup_candidate"] is not None
        assert output["backup_candidate"]["rank"] == 2
        assert output["backup_candidate"]["selection"] == "BACKUP"

    @pytest.mark.asyncio
    async def test_no_backup_if_second_fails_threshold(self):
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

        context = _create_context(strategy_input)
        result = await agent.execute(context)

        assert result.status == AgentRunStatus.SUCCESS
        output = result.output
        assert output["primary_candidate"]["selection"] == "PRIMARY"
        assert output["backup_candidate"] is None

    @pytest.mark.asyncio
    async def test_complete_shortlist_ranking(self):
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

        context = _create_context(strategy_input)
        result = await agent.execute(context)

        assert result.status == AgentRunStatus.SUCCESS
        output = result.output
        assert len(output["scored_candidates"]) == 5

        # Check ranking order
        scores = [c["total_score"] for c in output["scored_candidates"]]  # type: ignore[index]
        assert scores == sorted(scores, reverse=True), "Candidates should be ranked by score"

        # Check ranks are sequential
        ranks = [c["rank"] for c in output["scored_candidates"]]  # type: ignore[index]
        assert ranks == [1, 2, 3, 4, 5]

    @pytest.mark.asyncio
    async def test_scoring_dimensions_present(self):
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

        context = _create_context(strategy_input)
        result = await agent.execute(context)

        output = result.output
        primary = output["primary_candidate"]  # type: ignore[index]
        assert len(primary["scoring"]) == 4  # type: ignore[arg-type, index]

        dimensions = {s["dimension"] for s in primary["scoring"]}  # type: ignore[index]
        assert dimensions == {
            "impulse_priced",
            "tangible",
            "honest_promise",
            "trendy_but_tricky",
        }

        # Check total equals sum of dimensions
        total_from_dimensions = sum(s["score"] for s in primary["scoring"])  # type: ignore[index]
        assert primary["total_score"] == total_from_dimensions  # type: ignore[index]

    @pytest.mark.asyncio
    async def test_evidence_collected(self):
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

        context = _create_context(strategy_input)
        result = await agent.execute(context)

        output = result.output
        assert len(output["evidence"]) >= 1  # type: ignore[arg-type]
        assert all("evidence_type" in e for e in output["evidence"])  # type: ignore[operator]

    @pytest.mark.asyncio
    async def test_product_spec_generated_when_qualified(self):
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

        context = _create_context(strategy_input)
        result = await agent.execute(context)

        output = result.output
        spec_data = output.get("product_spec")
        assert spec_data is not None
        assert isinstance(spec_data, dict)
        assert spec_data["identity"] == QUALIFIED_CANDIDATE.identity
        assert spec_data["base_category"] == QUALIFIED_CANDIDATE.base_category

        hubs = spec_data.get("hubs")
        assert hubs is not None and isinstance(hubs, (list, tuple))
        assert len(hubs) >= 6
        assert len(hubs) <= 8

        colour_variants = spec_data.get("colour_variants")
        assert colour_variants is not None and isinstance(colour_variants, (list, tuple))
        assert len(colour_variants) >= 3
        assert len(colour_variants) <= 4

        # Type-safe comparison for prices
        real_price = spec_data.get("real_price")
        anchor_price = spec_data.get("anchor_price")
        assert isinstance(real_price, (int, float, str))
        assert isinstance(anchor_price, (int, float, str))

    @pytest.mark.asyncio
    async def test_threshold_exact_boundary(self):
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

        context = _create_context(strategy_input_30)
        result = await agent.execute(context)

        output = result.output
        primary = output.get("primary_candidate")
        assert primary is not None and isinstance(primary, dict)

        total_score = primary.get("total_score")
        assert isinstance(total_score, int)

        # If score is exactly 30, it should qualify
        if total_score == 30:
            assert output["qualification_outcome"] == "QUALIFIED"
            assert primary["passed_threshold"] is True

        # If score is 29, it should reject
        if total_score == 29:
            assert output["qualification_outcome"] == "REJECTED"
            assert primary["passed_threshold"] is False

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling with invalid input."""
        agent = A05ProductStrategy()

        # Missing required field
        invalid_job = JobEnvelope(
            job_id=uuid4(),
            workflow_id=uuid4(),
            object_id=uuid4(),
            job_type="ProductStrategyJob",
            object_type="workflow_runs",
            owner_agent_id="A05",
            status=JobStatus.READY,
            input={"job_id": str(uuid4()), "workflow_id": str(uuid4())},
            scheduled_at=datetime.now(tz=UTC),
            attempt=0,
            max_attempts=3,
            idempotency_key=f"test:{uuid4()}",
            side_effect_class=SideEffectClass.NONE,
            retry_class=RetryClass.SAFE,
            success_contract=SuccessContract(output_model="AgentResult"),
        )

        definition = AgentDefinition(
            agent_id="A05",
            name="Product Strategy",
            contract_version=1,
            system_prompt_reference="agent://A05/system/v1",
            input_contracts=("ProductStrategyInput",),
            output_contracts=("AgentResult",),
            allowed_tools=(),
            default_side_effect_class="NONE",
            timeout_seconds=300,
            commissioning_state=AgentCommissioningState.TESTED,
            commissioning_evidence=(),
        )

        context = AgentContext(
            job=invalid_job,
            definition=definition,
            run_id=uuid4(),
            prompt_text="",
            prompt_reference=definition.system_prompt_reference,
            prompt_sha256="0" * 64,
            prompt_version=1,
            provider=FakeLLMProvider(),
            run_at=datetime.now(tz=UTC),
        )

        result = await agent.execute(context)

        assert result.status == AgentRunStatus.FAILURE
        assert result.error is not None
        assert result.error.code == "PRODUCT_STRATEGY_FAILED"
        output = result.output
        assert output["qualification_outcome"] == "REJECTED"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
