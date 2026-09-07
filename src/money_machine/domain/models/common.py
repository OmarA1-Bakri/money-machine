"""References and supporting records shared by domain contracts."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, JsonValue, model_validator

from money_machine.domain.events import EventName
from money_machine.domain.models._base import (
    ContractModel,
    JsonObject,
    NonEmptyStr,
    NonNegativeInt,
    Sha256Hex,
    UtcDatetime,
)


class ArtifactReference(ContractModel):
    """Immutable identity and provenance for produced artifact bytes."""

    artifact_id: UUID
    logical_role: NonEmptyStr
    media_type: NonEmptyStr
    sha256: Sha256Hex
    byte_size: NonNegativeInt
    storage_reference: NonEmptyStr
    producing_job_id: UUID
    producing_agent_run_id: UUID
    created_at: UtcDatetime
    sensitivity: Literal["PUBLIC", "INTERNAL", "DENIED"]
    retention_class: NonEmptyStr
    parent_artifact_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def validate_parent_ids(self) -> Self:
        if self.artifact_id in self.parent_artifact_ids:
            raise ValueError("artifact cannot be its own parent")
        if len(set(self.parent_artifact_ids)) != len(self.parent_artifact_ids):
            raise ValueError("parent artifact IDs must be unique")
        return self


class EvidenceReference(ContractModel):
    """Opaque, safe reference to durable decision or verification evidence."""

    evidence_id: UUID
    evidence_type: NonEmptyStr
    source_reference: NonEmptyStr
    observed_at: UtcDatetime
    sha256: Sha256Hex | None = None
    artifact_id: UUID | None = None
    producing_job_id: UUID | None = None
    safe_summary: NonEmptyStr


class EffectReference(ContractModel):
    """Reconcilable identity of one attempted external effect (D-0025)."""

    idempotency_key: NonEmptyStr
    provider: NonEmptyStr
    operation: NonEmptyStr
    provider_object_id: NonEmptyStr | None = None
    effect_state: Literal["CONFIRMED", "ABSENT", "UNKNOWN"]
    observed_at: UtcDatetime
    reconciliation_attempt: NonNegativeInt = 0

    @model_validator(mode="after")
    def validate_effect_state(self) -> Self:
        if self.effect_state == "CONFIRMED" and self.provider_object_id is None:
            raise ValueError("a confirmed effect must identify the provider object")
        if self.effect_state == "ABSENT" and self.provider_object_id is not None:
            raise ValueError("an absent effect cannot identify a provider object")
        return self


class ContractError(ContractModel):
    """Structured agent, blocker, or incident error without sensitive payloads."""

    code: NonEmptyStr
    message: NonEmptyStr
    retryable: bool = False
    blocker_action: NonEmptyStr | None = None
    safe_detail: JsonObject = Field(default_factory=dict)


class SuccessContract(ContractModel):
    """Required output, artifacts, and events for atomic job completion."""

    output_model: NonEmptyStr
    required_artifact_roles: tuple[NonEmptyStr, ...] = ()
    required_events: tuple[EventName, ...] = ()

    @model_validator(mode="after")
    def validate_uniqueness(self) -> Self:
        if len(set(self.required_artifact_roles)) != len(self.required_artifact_roles):
            raise ValueError("required artifact roles must be unique")
        if len(set(self.required_events)) != len(self.required_events):
            raise ValueError("required events must be unique")
        return self


class CheckResult(ContractModel):
    """One named QA or preflight check with cited evidence."""

    name: NonEmptyStr
    passed: bool
    defect_code: NonEmptyStr | None = None
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    observed_value: JsonValue | None = None

    @model_validator(mode="after")
    def validate_defect_code(self) -> Self:
        if self.passed and self.defect_code is not None:
            raise ValueError("passing check forbids a defect code")
        if not self.passed and self.defect_code is None:
            raise ValueError("failed check requires a defect code")
        return self
