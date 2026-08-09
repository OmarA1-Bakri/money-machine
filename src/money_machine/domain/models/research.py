"""Research evidence and packet contracts."""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import AnyHttpUrl, AwareDatetime, Field, field_serializer, field_validator

from money_machine.domain.enums import QualificationDimension
from money_machine.domain.value_objects import FrozenModel, NonEmptyStr, Sha256, immutable_mapping


class EvidenceReference(FrozenModel):
    """Immutable provenance for one admitted observation."""

    evidence_id: NonEmptyStr
    source_url: AnyHttpUrl
    observed_at: AwareDatetime
    source_mode: Literal["manual_export", "connector_read", "fixture"]
    freshness_status: Literal["current", "stale", "unknown"]
    content_sha256: Sha256


class ResearchObservation(FrozenModel):
    """One provider-neutral marketplace observation."""

    observation_id: NonEmptyStr
    evidence: EvidenceReference
    marketplace: NonEmptyStr
    title: NonEmptyStr
    category: NonEmptyStr
    identity_niche: NonEmptyStr
    base_category: NonEmptyStr
    price: Decimal | None
    currency: NonEmptyStr | None
    demand_proxies: Mapping[str, Decimal]
    competition_proxies: Mapping[str, Decimal]
    qualification_inputs: Mapping[QualificationDimension, Decimal]
    listing_quality_notes: tuple[str, ...]

    @field_validator("demand_proxies", "competition_proxies", mode="after")
    @classmethod
    def freeze_decimal_proxies(cls, value: Mapping[str, Decimal]) -> Mapping[str, Decimal]:
        return immutable_mapping(value)

    @field_validator("qualification_inputs", mode="after")
    @classmethod
    def freeze_qualification_inputs(
        cls, value: Mapping[QualificationDimension, Decimal]
    ) -> Mapping[QualificationDimension, Decimal]:
        return immutable_mapping(value)

    @field_serializer("demand_proxies", "competition_proxies")
    def serialize_decimal_proxies(self, value: Mapping[str, Decimal]) -> dict[str, Decimal]:
        return dict(value)

    @field_serializer("qualification_inputs")
    def serialize_qualification_inputs(
        self, value: Mapping[QualificationDimension, Decimal]
    ) -> dict[QualificationDimension, Decimal]:
        return dict(value)


class ResearchPacket(FrozenModel):
    """An admitted, bounded set of research observations."""

    packet_id: NonEmptyStr
    imported_at: AwareDatetime
    observations: Annotated[tuple[ResearchObservation, ...], Field(min_length=25, max_length=40)]
    packet_sha256: Sha256


__all__ = ["EvidenceReference", "ResearchObservation", "ResearchPacket", "datetime"]
