"""Typed event names and append-only event envelope."""

from collections.abc import Mapping
from enum import StrEnum
from typing import cast
from uuid import UUID

from pydantic import AwareDatetime, field_serializer, field_validator

from money_machine.domain.value_objects import (
    FrozenModel,
    Sha256,
    freeze_canonical_value,
    thaw_canonical_value,
)


class DomainEventName(StrEnum):
    """Exact events emitted by the first-product workflow."""

    RESEARCH_PACKET_ADMITTED = "research_packet_admitted"
    CANDIDATE_SHORTLISTED = "candidate_shortlisted"
    PRODUCT_SPEC_CREATED = "product_spec_created"
    DEDUPE_PASSED = "dedupe_passed"
    PRODUCT_BUILT = "product_built"
    PRODUCT_QA_PASSED = "product_qa_passed"
    LISTING_PACKAGE_CREATED = "listing_package_created"
    PREFLIGHT_PASSED = "preflight_passed"
    DRAFT_READY = "draft_ready"


class DomainEvent(FrozenModel):
    """Schema-versioned event persisted with a canonical payload hash."""

    event_id: UUID
    workflow_run_id: UUID
    job_id: UUID | None
    name: DomainEventName
    occurred_at: AwareDatetime
    payload: Mapping[str, object]
    payload_sha256: Sha256

    @field_validator("payload", mode="after")
    @classmethod
    def freeze_payload(cls, value: Mapping[str, object]) -> Mapping[str, object]:
        return cast(Mapping[str, object], freeze_canonical_value(value))

    @field_serializer("payload")
    def serialize_payload(self, value: Mapping[str, object]) -> dict[str, object]:
        return cast(dict[str, object], thaw_canonical_value(value))
