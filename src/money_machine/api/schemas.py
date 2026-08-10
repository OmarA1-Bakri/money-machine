"""Strict path-redacted response contracts for the read-only operator API."""

from __future__ import annotations

from pathlib import PurePosixPath, PureWindowsPath
from typing import Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator, model_validator


class ResponseModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class BlockerResponse(ResponseModel):
    code: str
    message: str
    result_type: str | None
    result_id: str | None
    result_sha256: str | None
    occurred_at: AwareDatetime


class WorkflowResponse(ResponseModel):
    workflow_run_id: UUID
    workflow_type: str
    packet_id: str
    state: str
    created_at: AwareDatetime
    updated_at: AwareDatetime
    terminal_blocker: BlockerResponse | None


class JobResponse(ResponseModel):
    job_id: UUID
    job_type: str
    state: str
    retry_class: str
    max_attempts: int


class ProductFactResponse(ResponseModel):
    claim: str
    category: str
    evidence_ids: tuple[str, ...]


class ProductResponse(ResponseModel):
    product_spec_id: str
    candidate_id: str
    identity_niche: str
    base_category: str
    target_buyer: str
    promised_outcome: str
    hubs: tuple[str, ...]
    colour_variants: tuple[str, ...]
    features: tuple[str, ...]
    product_facts: tuple[ProductFactResponse, ...]
    source_evidence_ids: tuple[str, ...]
    spec_sha256: str


class ArtifactSummary(ResponseModel):
    artifact_id: str
    relative_path: str
    media_type: str
    byte_count: int
    sha256: str

    @field_validator("relative_path")
    @classmethod
    def require_relative_posix_path(cls, value: str) -> str:
        if (
            "\\" in value
            or not value
            or PurePosixPath(value).is_absolute()
            or bool(PureWindowsPath(value).drive)
        ):
            raise ValueError("artifact path must be relative POSIX")
        if ".." in PurePosixPath(value).parts:
            raise ValueError("artifact path cannot traverse")
        return value


class ListingResponse(ResponseModel):
    listing_package_id: str
    product_spec_id: str
    build_id: str
    title: str
    description: str
    tags: tuple[str, ...]
    feature_statements: tuple[str, ...]
    buyer_fit_statements: tuple[str, ...]
    listing_images: tuple[ArtifactSummary, ...]
    preview_video: ArtifactSummary | None
    preview_video_status: str
    delivery_document: ArtifactSummary | None
    package_manifest: ArtifactSummary | None
    package_sha256: str

    @model_validator(mode="after")
    def require_generated_video(self) -> Self:
        if self.preview_video_status != "GENERATED" or self.preview_video is None:
            raise ValueError("DRAFT_READY listing requires generated video")
        return self
