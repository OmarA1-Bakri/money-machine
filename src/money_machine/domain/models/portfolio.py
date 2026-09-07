"""Metrics, portfolio-decision, and incident result contracts."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from money_machine.domain.enums import DecisionType, IncidentType
from money_machine.domain.events import EventName
from money_machine.domain.models._base import (
    ContractModel,
    CurrencyCode,
    NonEmptyStr,
    NonNegativeDecimal,
    NonNegativeInt,
    PositiveInt,
    UtcDatetime,
)
from money_machine.domain.models.common import ContractError, EvidenceReference


class MetricsSnapshot(ContractModel):
    """Append-only reconciled provider metrics observation."""

    snapshot_id: UUID
    listing_id: UUID
    listing_version: PositiveInt
    provider: NonEmptyStr
    observed_at: UtcDatetime
    views: NonNegativeInt
    favourites: NonNegativeInt
    orders: NonNegativeInt
    gross_revenue: NonNegativeDecimal
    currency: CurrencyCode
    reconciled: bool
    source_evidence: tuple[EvidenceReference, ...] = Field(min_length=1)


class PortfolioDecision(ContractModel):
    """Evidence-backed HOLD, REPAIR, CULL, or MULTIPLY branch result."""

    decision_id: UUID
    workflow_id: UUID
    product_id: UUID
    listing_id: UUID
    decision: DecisionType
    metrics_snapshot_ids: tuple[UUID, ...] = Field(min_length=1)
    cohort_reference: NonEmptyStr
    rule_version: NonEmptyStr
    explanation: NonEmptyStr
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    repair_job_id: UUID | None = None
    deactivation_job_id: UUID | None = None
    successor_workflow_id: UUID | None = None
    successor_spec_id: UUID | None = None
    decided_at: UtcDatetime

    @model_validator(mode="after")
    def validate_decision_path(self) -> Self:
        if len(set(self.metrics_snapshot_ids)) != len(self.metrics_snapshot_ids):
            raise ValueError("metrics snapshot IDs must be unique")

        if self.decision is DecisionType.HOLD:
            if any(
                value is not None
                for value in (
                    self.repair_job_id,
                    self.deactivation_job_id,
                    self.successor_workflow_id,
                    self.successor_spec_id,
                )
            ):
                raise ValueError("HOLD forbids repair, deactivation, and successor IDs")
        elif self.decision is DecisionType.REPAIR:
            if self.repair_job_id is None:
                raise ValueError("REPAIR requires repair_job_id")
            if any(
                value is not None
                for value in (
                    self.deactivation_job_id,
                    self.successor_workflow_id,
                    self.successor_spec_id,
                )
            ):
                raise ValueError("REPAIR forbids deactivation and successor IDs")
        elif self.decision is DecisionType.CULL:
            if self.deactivation_job_id is None:
                raise ValueError("CULL requires deactivation_job_id")
            if any(
                value is not None
                for value in (
                    self.repair_job_id,
                    self.successor_workflow_id,
                    self.successor_spec_id,
                )
            ):
                raise ValueError("CULL forbids repair and successor IDs")
        elif self.decision is DecisionType.MULTIPLY:
            if self.successor_workflow_id is None:
                raise ValueError("MULTIPLY requires successor_workflow_id")
            if self.successor_spec_id is None:
                raise ValueError("MULTIPLY requires successor_spec_id")
            if self.successor_workflow_id == self.workflow_id:
                raise ValueError("successor workflow must differ from parent workflow")
            if self.repair_job_id is not None or self.deactivation_job_id is not None:
                raise ValueError("MULTIPLY forbids repair and deactivation IDs")
        return self


class IncidentResult(ContractModel):
    """Typed incident state or verified resolution result."""

    result_id: UUID
    incident_id: UUID
    incident_type: IncidentType
    status: Literal["OPEN", "BLOCKED", "RESOLVED", "UNCERTAIN_EXTERNAL_EFFECT"]
    affected_object_type: NonEmptyStr
    affected_object_id: UUID
    affected_version: PositiveInt
    opening_event: EventName
    opening_job_id: UUID
    safe_detail: NonEmptyStr
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    resolution_job_id: UUID | None = None
    resolution_result_reference: NonEmptyStr | None = None
    error: ContractError | None = None
    opened_at: UtcDatetime
    resolved_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def validate_incident_status(self) -> Self:
        resolution_fields = (
            self.resolution_job_id,
            self.resolution_result_reference,
            self.resolved_at,
        )
        if self.status == "RESOLVED":
            if any(value is None for value in resolution_fields):
                raise ValueError("RESOLVED requires resolution job, result, and timestamp")
            if self.error is not None:
                raise ValueError("RESOLVED forbids an error")
        else:
            if any(value is not None for value in resolution_fields):
                raise ValueError("unresolved incident forbids resolution fields")
            if self.status in {"BLOCKED", "UNCERTAIN_EXTERNAL_EFFECT"} and self.error is None:
                raise ValueError(f"{self.status} requires an error")
        if self.resolved_at is not None and self.resolved_at < self.opened_at:
            raise ValueError("resolved_at cannot precede opened_at")
        return self
