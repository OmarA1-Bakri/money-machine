"""Listing package and fail-closed preflight contracts."""

from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from money_machine.domain.models.asset import ArtifactReference
from money_machine.domain.value_objects import FrozenModel, NonEmptyStr, Sha256

ListingTitle = Annotated[str, StringConstraints(min_length=1, max_length=140)]
ListingTag = Annotated[str, StringConstraints(min_length=1, max_length=20)]


class ListingPackage(FrozenModel):
    """Truth-bound listing copy plus deterministic creative artifacts."""

    listing_package_id: NonEmptyStr
    product_spec_id: NonEmptyStr
    build_id: NonEmptyStr
    title: ListingTitle
    description: NonEmptyStr
    tags: Annotated[tuple[ListingTag, ...], Field(min_length=13, max_length=13)]
    feature_statements: tuple[str, ...]
    buyer_fit_statements: tuple[str, ...]
    listing_images: tuple[ArtifactReference, ...] = ()
    preview_video: ArtifactReference | None = None
    preview_video_status: Literal["PENDING", "GENERATED", "NOT_GENERATED"] = "PENDING"
    delivery_document: ArtifactReference | None = None
    package_manifest: ArtifactReference | None = None
    package_sha256: Sha256

    @model_validator(mode="after")
    def validate_unique_tags_and_video(self) -> Self:
        """Reject tag duplication and contradictory video status."""

        if len(set(self.tags)) != len(self.tags):
            raise ValueError("listing tags must be unique")
        if (self.preview_video_status == "GENERATED") != (self.preview_video is not None):
            raise ValueError("preview video status and artifact conflict")
        return self


class PreflightResult(FrozenModel):
    """Fail-closed draft-readiness verdict with zero-effect invariants."""

    preflight_result_id: NonEmptyStr
    listing_package_id: NonEmptyStr
    passed: bool
    findings: tuple[str, ...]
    checked_at: AwareDatetime
    external_effect_mode: Literal["simulation", "draft"]
    incremental_spend: Decimal
    publication_receipt_present: Literal[False]
    result_sha256: Sha256

    @model_validator(mode="after")
    def validate_zero_spend(self) -> Self:
        """The first slice never permits incremental spend."""

        if self.incremental_spend != Decimal("0.00"):
            raise ValueError("incremental_spend must be exactly 0.00")
        return self
