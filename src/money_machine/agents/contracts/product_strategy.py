"""A05 Product Strategy agent contract — Low-Ticket scoring and ProductSpec generation."""

from typing import Literal
from uuid import UUID

from pydantic import Field

from money_machine.domain.enums import AgentRunStatus
from money_machine.domain.models._base import (
    ContractModel,
    NonEmptyStr,
    NonNegativeInt,
    PositiveInt,
    UtcDatetime,
)
from money_machine.domain.models.common import ArtifactReference, ContractError, EvidenceReference
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.models.research import CandidateProfile


class ProductStrategyInput(ContractModel):
    """Input for A05 Product Strategy agent."""

    job_id: UUID
    workflow_id: UUID
    research_run_id: UUID
    candidates: tuple[CandidateProfile, ...] = Field(min_length=1, max_length=5)
    scoring_threshold: PositiveInt = 30
    maximum_score: PositiveInt = 40


class ScoringReasoning(ContractModel):
    """Concise reasoning for one scoring dimension."""

    dimension: Literal[
        "impulse_priced",
        "tangible",
        "honest_promise",
        "trendy_but_tricky",
    ]
    score: NonNegativeInt
    reasoning: NonEmptyStr = Field(max_length=500)
    evidence_refs: tuple[NonEmptyStr, ...] = Field(min_length=1)


class ScoredCandidate(ContractModel):
    """One candidate with complete scoring breakdown."""

    candidate: CandidateProfile
    scoring: tuple[ScoringReasoning, ...] = Field(min_length=4, max_length=4)
    total_score: NonNegativeInt
    passed_threshold: bool
    rank: PositiveInt
    selection: Literal["PRIMARY", "BACKUP", "REJECTED"]


class ProductStrategyResult(ContractModel):
    """Output from A05 Product Strategy agent."""

    agent_run_id: UUID
    agent_id: Literal["A05"]
    agent_definition_version: PositiveInt
    prompt_reference: NonEmptyStr
    prompt_sha256: NonEmptyStr
    status: AgentRunStatus

    job_id: UUID
    workflow_id: UUID
    research_run_id: UUID
    scored_candidates: tuple[ScoredCandidate, ...] = Field(min_length=1, max_length=5)
    primary_candidate: ScoredCandidate
    backup_candidate: ScoredCandidate | None = None
    product_spec: ProductSpec | None = None

    qualification_outcome: Literal["QUALIFIED", "REJECTED"]
    artifacts: tuple[ArtifactReference, ...] = ()
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    error: ContractError | None = None
    completed_at: UtcDatetime
