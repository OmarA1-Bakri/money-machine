"""Durable job and terminal agent-run contracts."""

from typing import Self
from uuid import UUID

from pydantic import model_validator

from money_machine.domain.enums import (
    AgentRunStatus,
    JobStatus,
    RetryClass,
    SideEffectClass,
)
from money_machine.domain.events import EventName
from money_machine.domain.models._base import (
    AgentId,
    ContractModel,
    JsonObject,
    NonEmptyStr,
    NonNegativeInt,
    PositiveInt,
    Sha256Hex,
    UtcDatetime,
)
from money_machine.domain.models.common import (
    ArtifactReference,
    ContractError,
    EffectReference,
    EvidenceReference,
    SuccessContract,
)


class JobEnvelope(ContractModel):
    """Versioned, schedulable unit of durable workflow work."""

    job_id: UUID
    workflow_id: UUID
    object_id: UUID
    job_type: NonEmptyStr
    object_type: NonEmptyStr
    owner_agent_id: AgentId
    status: JobStatus
    input: JsonObject
    required_artifacts: tuple[ArtifactReference, ...] = ()
    scheduled_at: UtcDatetime
    attempt: NonNegativeInt
    max_attempts: PositiveInt
    idempotency_key: NonEmptyStr
    side_effect_class: SideEffectClass
    retry_class: RetryClass
    success_contract: SuccessContract

    @model_validator(mode="after")
    def validate_attempt_budget(self) -> Self:
        if self.attempt > self.max_attempts:
            raise ValueError("attempt cannot exceed max_attempts")
        artifact_ids = tuple(reference.artifact_id for reference in self.required_artifacts)
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("required artifacts must be unique")
        return self


class AgentResult(ContractModel):
    """Terminal structured result returned by one agent run."""

    job_id: UUID
    agent_run_id: UUID
    agent_id: AgentId
    agent_definition_version: PositiveInt
    prompt_reference: NonEmptyStr
    prompt_sha256: Sha256Hex
    status: AgentRunStatus
    output: JsonObject
    artifacts: tuple[ArtifactReference, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    emitted_events: tuple[EventName, ...] = ()
    effects: tuple[EffectReference, ...] = ()
    error: ContractError | None = None

    @model_validator(mode="after")
    def validate_terminal_result(self) -> Self:
        if self.status is AgentRunStatus.SUCCESS and self.error is not None:
            raise ValueError("SUCCESS forbids an error")
        if self.status is not AgentRunStatus.SUCCESS and self.error is None:
            raise ValueError("non-success result requires an error")
        for artifact in self.artifacts:
            if artifact.producing_agent_run_id != self.agent_run_id:
                raise ValueError("every produced artifact must cite this agent run")
            if artifact.producing_job_id != self.job_id:
                raise ValueError("every produced artifact must cite this job")
        effect_keys = tuple(effect.idempotency_key for effect in self.effects)
        if len(set(effect_keys)) != len(effect_keys):
            raise ValueError("effect references must be unique by idempotency key")
        if self.status is AgentRunStatus.UNCERTAIN_EXTERNAL_EFFECT and not any(
            effect.effect_state == "UNKNOWN" for effect in self.effects
        ):
            raise ValueError("an uncertain result must cite the unresolved effect")
        if len(set(self.emitted_events)) != len(self.emitted_events):
            raise ValueError("emitted events must be unique")
        artifact_ids = tuple(reference.artifact_id for reference in self.artifacts)
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("result artifacts must be unique")
        evidence_ids = tuple(reference.evidence_id for reference in self.evidence)
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("result evidence must be unique")
        return self
