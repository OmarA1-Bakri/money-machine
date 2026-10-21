"""Read-only persisted fixture completion and verified product bytes."""

from __future__ import annotations

import hashlib
import os
import stat
from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Response
from fastapi import Path as ApiPath
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Select, select
from sqlalchemy.exc import SQLAlchemyError

from money_machine.api.dependencies import SessionDependency
from money_machine.persistence.tables import (
    Artifact,
    Asset,
    EtsyListing,
    Job,
    ListingVersion,
    PreflightResult,
    Product,
    Shop,
    WorkflowRun,
)

router = APIRouter(prefix="/operator/runs", tags=["operator"])
RunId = Annotated[str, ApiPath(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]


class ProofModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProofJob(ProofModel):
    id: UUID
    job_type: str
    status: str


class ProofArtifact(ProofModel):
    id: UUID
    label: str
    kind: str
    media_type: str
    byte_size: int
    href: str


class RunSummary(ProofModel):
    run_id: str
    workflow_id: UUID
    product_id: UUID
    listing_version_id: UUID
    product_title: str
    fixture_completed: bool
    completed_at: datetime | None
    product_state: str
    jobs: list[ProofJob]
    artifacts: list[ProofArtifact]


def _artifact_query(run_id: str) -> Select[tuple[Artifact, Asset]]:
    return (
        select(Artifact, Asset)
        .join(Asset, Asset.artifact_id == Artifact.id)
        .join(Product, Asset.product_id == Product.id)
        .join(WorkflowRun, Product.workflow_id == WorkflowRun.id)
        .join(Shop, Product.shop_id == Shop.id)
        .where(Shop.name == "fixture:" + run_id, WorkflowRun.shop_id == Shop.id)
    )


@router.get("/{run_id}/summary", response_model=RunSummary)
async def run_summary(run_id: RunId, session: SessionDependency) -> RunSummary:
    try:
        selected = (
            await session.execute(
                select(Product, WorkflowRun, ListingVersion)
                .join(WorkflowRun, Product.workflow_id == WorkflowRun.id)
                .join(Shop, Product.shop_id == Shop.id)
                .join(EtsyListing, EtsyListing.product_id == Product.id)
                .join(ListingVersion, ListingVersion.listing_id == EtsyListing.id)
                .where(
                    Shop.name == "fixture:" + run_id,
                    WorkflowRun.shop_id == Shop.id,
                    EtsyListing.shop_id == Shop.id,
                    ListingVersion.product_id == Product.id,
                )
                .order_by(
                    Product.created_at.desc(),
                    Product.id.desc(),
                    (
                        ListingVersion.qa_result_id.is_not(None)
                        & select(PreflightResult.id)
                        .where(
                            PreflightResult.listing_version_id == ListingVersion.id,
                            PreflightResult.listing_package_sha256 == ListingVersion.package_sha256,
                            PreflightResult.outcome == "PASS",
                        )
                        .exists()
                    ).desc(),
                    ListingVersion.listing_version.desc(),
                    ListingVersion.created_at.desc(),
                    ListingVersion.id.desc(),
                )
                .limit(1)
            )
        ).first()
        if selected is None:
            raise HTTPException(status_code=404, detail="fixture product not found")
        product, workflow, listing = selected
        jobs = await session.scalars(
            select(Job).where(Job.workflow_id == workflow.id).order_by(Job.created_at, Job.id)
        )
        artifacts = (
            await session.execute(
                _artifact_query(run_id)
                .where(Asset.product_id == product.id)
                .order_by(Asset.asset_role, Asset.ordinal, Artifact.id)
            )
        ).all()
        return RunSummary(
            run_id=run_id,
            workflow_id=workflow.id,
            product_id=product.id,
            listing_version_id=listing.id,
            product_title=product.working_title,
            fixture_completed=workflow.completed_at is not None,
            completed_at=workflow.completed_at,
            product_state=workflow.product_state,
            jobs=[ProofJob(id=job.id, job_type=job.job_type, status=job.status) for job in jobs],
            artifacts=[
                ProofArtifact(
                    id=artifact.id,
                    label=artifact.logical_role,
                    kind=asset.asset_role,
                    media_type="text/html"
                    if asset.asset_role == "product_html"
                    else artifact.media_type,
                    byte_size=artifact.byte_size,
                    href=f"/operator/runs/{run_id}/artifacts/{artifact.id}",
                )
                for artifact, asset in artifacts
            ],
        )
    except (SQLAlchemyError, OSError) as error:
        raise HTTPException(status_code=503, detail="operator database unavailable") from error


def _verified_bytes(artifact: Artifact, run_id: str) -> bytes:
    """Open each component without following symlinks, then verify that same file descriptor."""
    configured = os.environ.get("MONEY_MACHINE_EVIDENCE_ROOT", "/srv/work/evidence")
    root = Path(configured).resolve() / run_id / "e2e"
    reference = artifact.storage_reference
    path = Path(reference)
    if not path.is_absolute():
        raise ValueError("storage reference must be absolute")
    relative = path.relative_to(root)
    if not relative.parts or any(part in (".", "..") for part in relative.parts):
        raise ValueError("invalid artifact path")
    # Run and e2e must also be real directories, rather than links outside the evidence root.
    parts = (run_id, "e2e", *relative.parts)
    fd = os.open(root.parent.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for index, part in enumerate(parts):
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if index < len(parts) - 1:
                flags |= os.O_DIRECTORY
            next_fd = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("artifact is not a regular file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            content = stream.read(artifact.byte_size + 1)
        if (
            len(content) != artifact.byte_size
            or hashlib.sha256(content).hexdigest() != artifact.sha256
        ):
            raise ValueError("artifact integrity mismatch")
        return content
    finally:
        os.close(fd)


@router.get("/{run_id}/artifacts/{artifact_id}")
async def run_artifact(run_id: RunId, artifact_id: UUID, session: SessionDependency) -> Response:
    try:
        row = (
            await session.execute(
                _artifact_query(run_id).where(Artifact.id == artifact_id).limit(1)
            )
        ).first()
    except (SQLAlchemyError, OSError) as error:
        raise HTTPException(status_code=503, detail="operator database unavailable") from error
    if row is None:
        raise HTTPException(status_code=404, detail="fixture artifact not found")
    artifact, asset = row
    try:
        content = _verified_bytes(artifact, run_id)
    except (OSError, ValueError) as error:
        raise HTTPException(
            status_code=409, detail="fixture artifact unavailable or changed"
        ) from error
    return Response(
        content=content,
        media_type="text/html" if asset.asset_role == "product_html" else artifact.media_type,
        headers={
            "Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'; "
            "img-src data:; form-action 'none'; base-uri 'none'; frame-ancestors 'self'",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Content-Disposition": f'inline; filename="{artifact.id}"',
        },
    )
