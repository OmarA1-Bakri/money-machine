"""Typed, replay-safe local product export contracts."""

from decimal import Decimal
from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator, model_validator

from money_machine.domain.models.candidate import QualificationScore
from money_machine.domain.value_objects import FrozenModel, NonEmptyStr, Sha256

type ProductId = Annotated[str, StringConstraints(pattern=r"^PS-[0-9a-f]{24}$")]

FIRST_PRODUCT_EXPORT_STEPS = (
    "ADMIT_RESEARCH_PACKET",
    "QUALIFY_CANDIDATES",
    "CREATE_PRODUCT_SPEC",
    "CHECK_CATALOGUE_DEDUPE",
    "BUILD_PRODUCT",
    "RUN_PRODUCT_QA",
    "CREATE_LISTING_PACKAGE",
    "RUN_PREFLIGHT",
)


class ProductExportResult(FrozenModel):
    """One exact durable workflow-result identity included in an export."""

    step: NonEmptyStr
    result_type: NonEmptyStr
    result_id: NonEmptyStr
    sha256: Sha256


class ProductExportFile(FrozenModel):
    """One immutable exported file with source lineage."""

    relative_path: NonEmptyStr
    media_type: NonEmptyStr
    byte_count: int = Field(ge=0)
    sha256: Sha256
    source_kind: Literal["durable_result", "build_artifact", "listing_artifact", "derived"]
    source_id: NonEmptyStr

    @field_validator("relative_path")
    @classmethod
    def require_canonical_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if (
            not value
            or value in {".", ".."}
            or "\\" in value
            or value.startswith("./")
            or "//" in value
            or path.is_absolute()
            or bool(PureWindowsPath(value).drive)
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.as_posix() != value
        ):
            raise ValueError("export path must be canonical POSIX-relative")
        return value


class QualificationExport(FrozenModel):
    """The exact persisted score set associated with a shortlist."""

    packet_id: NonEmptyStr
    shortlist_id: NonEmptyStr
    scores: Annotated[tuple[QualificationScore, ...], Field(min_length=5, max_length=5)]


class ProductExportManifest(FrozenModel):
    """Commit-marker payload for one complete local product export."""

    product_id: ProductId
    product_spec_id: ProductId
    workflow_run_id: UUID
    packet_id: NonEmptyStr
    terminal_state: Literal["DRAFT_READY"]
    results: Annotated[tuple[ProductExportResult, ...], Field(min_length=8, max_length=8)]
    research_rows: int = Field(ge=25, le=40)
    candidates_scored: Literal[5]
    candidates_shortlisted: Literal[5]
    hubs: int = Field(ge=6, le=8)
    variants: int = Field(ge=3, le=4)
    tags: Literal[13]
    images: Literal[10]
    videos: Literal[1]
    access_pdfs: Literal[1]
    files: Annotated[tuple[ProductExportFile, ...], Field(min_length=1)]
    external_mutations: Literal[0]
    spend_usd: Decimal

    @model_validator(mode="after")
    def validate_export_identity(self) -> Self:
        if self.product_id != self.product_spec_id:
            raise ValueError("product export identity must equal ProductSpec identity")
        if tuple(item.step for item in self.results) != FIRST_PRODUCT_EXPORT_STEPS:
            raise ValueError("export results must match the exact eight workflow steps")
        paths = tuple(item.relative_path for item in self.files)
        if len(paths) != len(set(paths)):
            raise ValueError("export file paths must be unique")
        if self.spend_usd != Decimal("0.00"):
            raise ValueError("export spend must be exactly 0.00")
        return self


class ProductExportReceipt(FrozenModel):
    """Machine-readable receipt for one immutable local export."""

    product_id: ProductId
    workflow_run_id: UUID
    artifact_path: NonEmptyStr
    manifest_sha256: Sha256
    file_count: int = Field(ge=1)
    replayed: bool
    external_mutations: Literal[0]
    spend_usd: Decimal

    @model_validator(mode="after")
    def validate_zero_spend(self) -> Self:
        if self.spend_usd != Decimal("0.00"):
            raise ValueError("export spend must be exactly 0.00")
        return self


__all__ = [
    "FIRST_PRODUCT_EXPORT_STEPS",
    "ProductExportFile",
    "ProductExportManifest",
    "ProductExportReceipt",
    "ProductExportResult",
    "QualificationExport",
]
