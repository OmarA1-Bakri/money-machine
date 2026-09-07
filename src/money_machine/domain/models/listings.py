"""Immutable listing-package and launch-preflight contracts."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from money_machine.domain.enums import BranchOutcome
from money_machine.domain.models._base import (
    ContractModel,
    CurrencyCode,
    NonEmptyStr,
    PositiveDecimal,
    PositiveInt,
    Sha256Hex,
    UtcDatetime,
)
from money_machine.domain.models.common import (
    ArtifactReference,
    CheckResult,
    EvidenceReference,
)
from money_machine.domain.models.rules import ListingRules


class ListingPackage(ContractModel):
    """Complete immutable listing version prepared for provider draft or publish."""

    package_id: UUID
    workflow_id: UUID
    product_id: UUID
    spec_id: UUID
    listing_version: PositiveInt
    rules: ListingRules
    title: NonEmptyStr
    description_sections: tuple[NonEmptyStr, ...] = Field(min_length=1)
    tags: tuple[NonEmptyStr, ...] = Field(min_length=1)
    currency: CurrencyCode
    price: PositiveDecimal
    anchor_price: PositiveDecimal
    quantity: PositiveInt
    digital_product: Literal[True]
    media_artifacts: tuple[ArtifactReference, ...] = Field(min_length=1)
    delivery_artifacts: tuple[ArtifactReference, ...] = Field(min_length=1)
    claim_evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    package_sha256: Sha256Hex
    created_at: UtcDatetime

    @property
    def description(self) -> str:
        """Render the ordered description sections as one listing description."""
        return "\n\n".join(self.description_sections)

    @model_validator(mode="after")
    def validate_unique_components(self) -> Self:
        normalized_tags = tuple(tag.casefold() for tag in self.tags)
        if len(set(normalized_tags)) != len(normalized_tags):
            raise ValueError("listing tags must be unique")

        artifact_ids = tuple(
            reference.artifact_id for reference in (*self.media_artifacts, *self.delivery_artifacts)
        )
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("listing artifacts must be unique")
        return self

    @model_validator(mode="after")
    def validate_playbook_shape(self) -> Self:
        """Bind the configured playbook listing shape (workbook §7) into the package."""
        rules = self.rules
        if len(self.tags) != rules.tags:
            raise ValueError(f"listing requires exactly {rules.tags} tags, got {len(self.tags)}")
        if len(self.description_sections) != rules.description_sections:
            raise ValueError(
                f"listing description requires exactly {rules.description_sections} sections, "
                f"got {len(self.description_sections)}"
            )
        images = sum(1 for item in self.media_artifacts if item.logical_role == rules.image_role)
        videos = sum(1 for item in self.media_artifacts if item.logical_role == rules.video_role)
        if images != rules.images:
            raise ValueError(f"listing requires exactly {rules.images} images, got {images}")
        if videos != rules.videos:
            raise ValueError(f"listing requires exactly {rules.videos} videos, got {videos}")
        if images + videos != len(self.media_artifacts):
            raise ValueError("listing media artifacts must all be listing images or videos")
        if self.quantity != rules.quantity:
            raise ValueError(f"listing quantity must be {rules.quantity}, got {self.quantity}")
        if self.anchor_price < self.price:
            raise ValueError("anchor_price must be at least the listing price")
        return self


class PreflightResult(ContractModel):
    """Launch-readiness outcome covering one immutable listing package."""

    result_id: UUID
    listing_package_id: UUID
    listing_package_sha256: Sha256Hex
    outcome: BranchOutcome
    checks: tuple[CheckResult, ...] = Field(min_length=1)
    repair_job_types: tuple[NonEmptyStr, ...]
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    completed_at: UtcDatetime

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        failed_checks = tuple(check for check in self.checks if not check.passed)
        if self.outcome not in {BranchOutcome.PASS, BranchOutcome.FAIL}:
            raise ValueError("PreflightResult outcome must be PASS or FAIL")
        if self.outcome is BranchOutcome.PASS and failed_checks:
            raise ValueError("PASS requires every check to pass")
        if self.outcome is BranchOutcome.PASS and self.repair_job_types:
            raise ValueError("PASS forbids repair jobs")
        if self.outcome is BranchOutcome.FAIL and not failed_checks:
            raise ValueError("FAIL requires a failed check")
        if self.outcome is BranchOutcome.FAIL and not self.repair_job_types:
            raise ValueError("FAIL requires a repair job")
        return self
