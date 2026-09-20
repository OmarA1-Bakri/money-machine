"""A05 Product Strategy Agent — Low-Ticket scoring and ProductSpec generation.

Implements the playbook's four scoring dimensions (§6):
1. Impulse-priced (10 points)
2. Tangible (10 points)
3. Honest promise (10 points)
4. Trendy but not tricky (10 points)

Total: 40 points. Threshold: 30 points minimum to qualify.
"""

import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

from money_machine.agents.base import AgentContext, BaseAgent
from money_machine.agents.contracts.product_strategy import (
    ProductStrategyInput,
    ProductStrategyResult,
    ScoredCandidate,
    ScoringReasoning,
)
from money_machine.domain.enums import AgentRunStatus
from money_machine.domain.models._base import JsonObject
from money_machine.domain.models.common import ContractError, EvidenceReference
from money_machine.domain.models.jobs import AgentResult
from money_machine.domain.models.product_spec import ColourToken, Hub, ProductSpec
from money_machine.domain.models.research import ProductCandidate


class A05ProductStrategy(BaseAgent):
    """Low-Ticket scorer and ProductSpec generator."""

    agent_id = "A05"

    async def execute(self, context: AgentContext) -> AgentResult:
        """Score candidates and generate ProductSpec for qualified primary."""
        try:
            # Parse input, allowing string UUIDs to be converted
            input_data = context.job.input
            if isinstance(input_data.get("job_id"), str):
                input_data["job_id"] = UUID(input_data["job_id"])  # type: ignore[assignment]
            if isinstance(input_data.get("workflow_id"), str):
                input_data["workflow_id"] = UUID(input_data["workflow_id"])  # type: ignore[assignment]
            if isinstance(input_data.get("research_run_id"), str):
                input_data["research_run_id"] = UUID(input_data["research_run_id"])  # type: ignore[assignment]
            # Convert candidates list back to tuple
            if isinstance(input_data.get("candidates"), list):
                input_data["candidates"] = tuple(input_data["candidates"])  # type: ignore[assignment]

            strategy_input = ProductStrategyInput.model_validate(input_data)

            # Score all candidates
            scored = self._score_candidates(strategy_input)

            # Rank by total score
            ranked = sorted(scored, key=lambda c: c.total_score, reverse=True)

            # Select primary and backup
            primary, backup = self._select_candidates(ranked, strategy_input.scoring_threshold)

            # Determine qualification outcome
            qualified = primary.passed_threshold
            outcome = "QUALIFIED" if qualified else "REJECTED"

            # Generate ProductSpec if qualified
            product_spec = None
            if qualified:
                product_spec = self._generate_product_spec(
                    primary.candidate,
                    strategy_input.workflow_id,
                    strategy_input.job_id,
                    context.agent_run_id,
                    strategy_input.research_run_id,
                )

            # Collect evidence
            evidence = self._collect_evidence(scored, strategy_input)

            result = ProductStrategyResult(
                agent_run_id=context.agent_run_id,
                agent_id="A05",
                agent_definition_version=context.definition.contract_version,
                prompt_reference=context.prompt_reference,
                prompt_sha256=context.prompt_sha256,
                status=AgentRunStatus.SUCCESS,
                job_id=strategy_input.job_id,
                workflow_id=strategy_input.workflow_id,
                research_run_id=strategy_input.research_run_id,
                scored_candidates=tuple(ranked),
                primary_candidate=primary,
                backup_candidate=backup,
                product_spec=product_spec,
                qualification_outcome=outcome,
                evidence=evidence,
                completed_at=datetime.now(UTC),
            )

            return AgentResult(
                job_id=context.job.job_id,
                agent_run_id=context.agent_run_id,
                agent_id="A05",
                agent_definition_version=context.definition.contract_version,
                prompt_reference=context.prompt_reference,
                prompt_sha256=context.prompt_sha256,
                status=AgentRunStatus.SUCCESS,
                output=cast(JsonObject, result.model_dump()),
                evidence=evidence,
            )

        except Exception as e:
            # Log the full exception for debugging
            import traceback

            print(f"PRODUCT_STRATEGY_FAILED: {e}")
            print(f"Traceback: {traceback.format_exc()}")

            error = ContractError(
                code="PRODUCT_STRATEGY_FAILED",
                message=str(e),
                retryable=False,
            )

            # Create minimal error output
            error_output = {
                "agent_run_id": str(context.agent_run_id),
                "agent_id": "A05",
                "agent_definition_version": context.definition.contract_version,
                "prompt_reference": context.prompt_reference,
                "prompt_sha256": context.prompt_sha256,
                "status": "FAILURE",
                "job_id": str(context.job.job_id),
                "workflow_id": str(context.job.input.get("workflow_id", uuid4())),
                "research_run_id": str(context.job.input.get("research_run_id", uuid4())),
                "qualification_outcome": "REJECTED",
                "error": error.model_dump(),
            }

            return AgentResult(
                job_id=context.job.job_id,
                agent_run_id=context.agent_run_id,
                agent_id="A05",
                agent_definition_version=context.definition.contract_version,
                prompt_reference=context.prompt_reference,
                prompt_sha256=context.prompt_sha256,
                status=AgentRunStatus.FAILURE,
                output=cast(JsonObject, error_output),
                error=error,
            )

    def _score_candidates(self, strategy_input: ProductStrategyInput) -> list[ScoredCandidate]:
        """Score each candidate across four dimensions."""
        scored: list[ScoredCandidate] = []

        for candidate in strategy_input.candidates:
            # Score each dimension (simplified stub logic)
            impulse_score = self._score_impulse_priced(candidate)
            tangible_score = self._score_tangible(candidate)
            honest_promise_score = self._score_honest_promise(candidate)
            trendy_score = self._score_trendy_but_tricky(candidate)

            total = impulse_score + tangible_score + honest_promise_score + trendy_score
            passed = total >= strategy_input.scoring_threshold

            scoring = (
                ScoringReasoning(
                    dimension="impulse_priced",
                    score=impulse_score,
                    reasoning=f"Price point analysis for {candidate.identity}",
                    evidence_refs=("research_observation",),
                ),
                ScoringReasoning(
                    dimension="tangible",
                    score=tangible_score,
                    reasoning=f"Tangibility assessment for {candidate.base_category}",
                    evidence_refs=("category_analysis",),
                ),
                ScoringReasoning(
                    dimension="honest_promise",
                    score=honest_promise_score,
                    reasoning=f"Promise clarity for {candidate.identity}",
                    evidence_refs=("market_observation",),
                ),
                ScoringReasoning(
                    dimension="trendy_but_tricky",
                    score=trendy_score,
                    reasoning=f"Trend analysis for {candidate.base_category}",
                    evidence_refs=("trend_data",),
                ),
            )

            # Update candidate with scores
            scored_candidate_dict = candidate.model_dump()
            scored_candidate_dict["impulse_priced_score"] = impulse_score
            scored_candidate_dict["tangible_score"] = tangible_score
            scored_candidate_dict["honest_promise_score"] = honest_promise_score
            scored_candidate_dict["trendy_but_tricky_score"] = trendy_score
            scored_candidate_dict["total_score"] = total

            updated_candidate = ProductCandidate.model_validate(scored_candidate_dict)

            scored.append(
                ScoredCandidate(
                    candidate=updated_candidate,
                    scoring=scoring,
                    total_score=total,
                    passed_threshold=passed,
                    rank=0,  # Will be set after sorting
                    selection="REJECTED",  # Will be updated in select phase
                )
            )

        return scored

    def _score_impulse_priced(self, candidate: ProductCandidate) -> int:
        """Score impulse pricing dimension (0-10 points)."""
        # Stub logic: actual implementation would analyze price bands from research
        if "Digital" in candidate.base_category or "Template" in candidate.identity:
            return 9
        return 7

    def _score_tangible(self, candidate: ProductCandidate) -> int:
        """Score tangibility dimension (0-10 points)."""
        # Stub logic: actual implementation would analyze deliverable structure
        if "Template" in candidate.identity or "Guide" in candidate.identity:
            return 9
        return 7

    def _score_honest_promise(self, candidate: ProductCandidate) -> int:
        """Score honest promise dimension (0-10 points)."""
        # Stub logic: actual implementation would analyze market messaging
        return 8

    def _score_trendy_but_tricky(self, candidate: ProductCandidate) -> int:
        """Score trendy but not tricky dimension (0-10 points)."""
        # Stub logic: actual implementation would analyze trend signals vs. complexity
        if any(risk.severity == "HIGH" for risk in candidate.risks):
            return 5
        return 8

    def _select_candidates(
        self, ranked: list[ScoredCandidate], threshold: int
    ) -> tuple[ScoredCandidate, ScoredCandidate | None]:
        """Select primary and backup from ranked candidates."""
        # Update ranks
        for i, candidate in enumerate(ranked, start=1):
            ranked[i - 1] = ScoredCandidate(
                candidate=candidate.candidate,
                scoring=candidate.scoring,
                total_score=candidate.total_score,
                passed_threshold=candidate.passed_threshold,
                rank=i,
                selection="REJECTED",
            )

        # Select primary (highest scoring)
        primary_data = ranked[0].model_dump()
        primary_data["selection"] = "PRIMARY"
        primary = ScoredCandidate.model_validate(primary_data)

        # Select backup (second highest, if exists and passes threshold)
        backup = None
        if len(ranked) > 1 and ranked[1].passed_threshold:
            backup_data = ranked[1].model_dump()
            backup_data["selection"] = "BACKUP"
            backup = ScoredCandidate.model_validate(backup_data)

        # Update remaining as REJECTED (already set in loop above)

        return primary, backup

    def _generate_product_spec(
        self,
        candidate: ProductCandidate,
        workflow_id: UUID,
        producing_job_id: UUID,
        producing_agent_run_id: UUID,
        research_run_id: UUID,
    ) -> ProductSpec:
        """Generate ProductSpec from qualified primary candidate."""
        # Generate concept fingerprint
        concept_data = f"{candidate.identity}:{candidate.base_category}"
        fingerprint = hashlib.sha256(concept_data.encode()).hexdigest()

        # Stub ProductSpec generation (would be more sophisticated in production)
        spec = ProductSpec(
            spec_id=uuid4(),
            product_id=uuid4(),  # Would be from product creation
            workflow_id=workflow_id,
            version=1,
            producing_job_id=producing_job_id,
            producing_agent_run_id=producing_agent_run_id,
            research_run_id=research_run_id,
            identity=candidate.identity,
            base_category=candidate.base_category,
            buyer_problem=f"Buyer needs {candidate.identity} for {candidate.base_category}",
            title=f"{candidate.identity} {candidate.base_category} Template",
            tier="mass",
            real_price=Decimal("9.99"),
            anchor_price=Decimal("19.99"),
            currency="USD",
            palette_name="Modern Minimalist",
            palette_tokens=(
                ColourToken(name="Primary", hex="#2C3E50"),
                ColourToken(name="Secondary", hex="#3498DB"),
                ColourToken(name="Accent", hex="#E74C3C"),
            ),
            hubs=(
                Hub(name="Introduction", description="Getting started guide", page_count=5),
                Hub(name="Core Content", description="Main content section", page_count=15),
                Hub(name="Templates", description="Ready-to-use templates", page_count=10),
                Hub(name="Examples", description="Real-world examples", page_count=8),
                Hub(name="Resources", description="Additional resources", page_count=7),
                Hub(name="Conclusion", description="Wrap-up and next steps", page_count=5),
            ),
            colour_variants=("Blue", "Green", "Purple"),
            flagship_feature="Complete step-by-step guide with templates",
            shared_databases=(),
            page_target_min=45,
            page_target_max=55,
            feature_targets=("Interactive examples", "Downloadable templates"),
            experiment_hypothesis=f"Testing {candidate.identity} with clear visual hierarchy",
            experiment_tags=("new-front",),
            concept_fingerprint=fingerprint,
            rule_version="v1",
            evidence=(
                EvidenceReference(
                    evidence_id=uuid4(),
                    evidence_type="scoring_analysis",
                    source_reference=f"candidate:{candidate.candidate_id}",
                    observed_at=datetime.now(UTC),
                    sha256=fingerprint,
                    safe_summary=f"Qualified with score {candidate.total_score}/40",
                ),
            ),
            created_at=datetime.now(UTC),
        )

        return spec

    def _collect_evidence(
        self, scored: list[ScoredCandidate], strategy_input: ProductStrategyInput
    ) -> tuple[EvidenceReference, ...]:
        """Collect evidence references from scoring."""
        evidence: list[EvidenceReference] = []

        for candidate in scored:
            evidence.append(
                EvidenceReference(
                    evidence_id=uuid4(),
                    evidence_type="candidate_scoring",
                    source_reference=f"research:{strategy_input.research_run_id}",
                    observed_at=datetime.now(UTC),
                    sha256=hashlib.sha256(
                        json.dumps(candidate.model_dump(), sort_keys=True).encode()
                    ).hexdigest(),
                    safe_summary=f"{candidate.candidate.identity}: {candidate.total_score}/40",
                )
            )

        return tuple(evidence)
