"""Read-only persisted fixture completion and verified product bytes."""

from __future__ import annotations

import asyncio
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
from money_machine.api.routers.operator_runs import (
    ExecutionMode,
    OperatorRun,
    select_operator_run,
)
from money_machine.persistence.tables import (
    AgentRun,
    Artifact,
    Asset,
    EffectAttempt,
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


class ProofRecovery(ProofModel):
    """Allowlisted persisted facts, independent of workflow/job completion."""

    job_id: UUID
    agent_run_id: UUID | None
    agent_run_status: str | None
    effect_state: str | None
    database_id: UUID | None
    data_source_id: UUID | None


class RunSummary(ProofModel):
    run_id: str
    workflow_id: UUID
    product_id: UUID
    listing_version_id: UUID | None
    product_title: str
    execution_mode: ExecutionMode
    fixture_completed: bool
    workflow_completed: bool
    pending_effects: int
    completed_at: datetime | None
    product_state: str
    jobs: list[ProofJob]
    recoveries: list[ProofRecovery]
    artifacts: list[ProofArtifact]


def _resource_id(value: object) -> UUID | None:
    if not isinstance(value, str):
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _recovery_proofs(
    product_id: UUID,
    jobs: list[Job],
    runs: list[AgentRun],
    effects: list[EffectAttempt],
) -> list[ProofRecovery]:
    latest_runs: dict[UUID, AgentRun] = {}
    for run in runs:  # Already ordered by descending run_number within each job.
        latest_runs.setdefault(run.job_id, run)
    proofs = []
    for job in jobs:
        record = job.input.get("notification_recovery")
        if (
            job.job_type != "BuildRepairJob"
            or job.owner_agent_id != "A07"
            or job.object_type != "Product"
            or job.object_id != product_id
            or not isinstance(record, dict)
        ):
            continue
        accepted = record.get("accepted_resource")
        accepted = accepted if isinstance(accepted, dict) else {}
        run = latest_runs.get(job.id)
        database_id = _resource_id(accepted.get("database_id"))
        observations = [
            effect
            for effect in effects
            if effect.job_id == job.id
            and effect.provider == "notion"
            and effect.operation == "notion.private_product.write"
            and effect.idempotency_key == record.get("effect_key")
        ]
        effect = observations[0] if len(observations) == 1 else None
        # A retained response is not proof that a different provider object was verified.
        if effect is not None and (
            (effect.effect_state == "CONFIRMED" or effect.provider_object_id is not None)
            and (database_id is None or _resource_id(effect.provider_object_id) != database_id)
        ):
            effect = None
        proofs.append(
            ProofRecovery(
                job_id=job.id,
                agent_run_id=run.id if run else None,
                agent_run_status=run.status if run else None,
                # Only the exact, identity-consistent recovery observation is eligible.
                effect_state=effect.effect_state if effect else None,
                database_id=database_id,
                data_source_id=_resource_id(accepted.get("data_source_id")),
            )
        )
    return proofs


def _artifact_query(selected: OperatorRun) -> Select[tuple[Artifact, Asset]]:
    return (
        select(Artifact, Asset)
        .join(Asset, Asset.artifact_id == Artifact.id)
        .join(Product, Asset.product_id == Product.id)
        .join(WorkflowRun, Product.workflow_id == WorkflowRun.id)
        .join(Shop, Product.shop_id == Shop.id)
        .where(
            Shop.id == selected.shop.id,
            WorkflowRun.shop_id == Shop.id,
            selected.workflow_scope(),
        )
    )


@router.get("/{run_id}/summary", response_model=RunSummary)
async def run_summary(run_id: RunId, session: SessionDependency) -> RunSummary:
    try:
        selected_run = await select_operator_run(session, run_id)
        selected = (
            await session.execute(
                select(Product, WorkflowRun, ListingVersion)
                .join(WorkflowRun, Product.workflow_id == WorkflowRun.id)
                .join(Shop, Product.shop_id == Shop.id)
                .outerjoin(
                    EtsyListing,
                    (EtsyListing.product_id == Product.id) & (EtsyListing.shop_id == Shop.id),
                )
                .outerjoin(
                    ListingVersion,
                    (ListingVersion.listing_id == EtsyListing.id)
                    & (ListingVersion.product_id == Product.id),
                )
                .where(
                    Shop.id == selected_run.shop.id,
                    selected_run.workflow_scope(),
                    WorkflowRun.shop_id == Shop.id,
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
            raise HTTPException(status_code=404, detail="operator product not found")
        product, workflow, listing = selected
        jobs = list(
            await session.scalars(
                select(Job).where(Job.workflow_id == workflow.id).order_by(Job.created_at, Job.id)
            )
        )
        runs = list(
            await session.scalars(
                select(AgentRun)
                .join(Job, AgentRun.job_id == Job.id)
                .where(Job.workflow_id == workflow.id, AgentRun.agent_id == "A07")
                .order_by(AgentRun.job_id, AgentRun.run_number.desc(), AgentRun.id.desc())
            )
        )
        artifacts = (
            await session.execute(
                _artifact_query(selected_run)
                .where(Asset.product_id == product.id)
                .order_by(Asset.asset_role, Asset.ordinal, Artifact.id)
            )
        ).all()
        # Historical UNKNOWN attempts remain durable; only the latest observation
        # per operation determines whether reconciliation is still required.
        effects = await session.scalars(
            select(EffectAttempt)
            .join(Job, EffectAttempt.job_id == Job.id)
            .where(Job.workflow_id == workflow.id)
            .order_by(EffectAttempt.idempotency_key, EffectAttempt.reconciliation_attempt.desc())
        )
        latest_effects: dict[str, EffectAttempt] = {}
        for effect in effects:
            latest_effects.setdefault(effect.idempotency_key, effect)
        pending_effects = sum(
            effect.effect_state == "UNKNOWN" for effect in latest_effects.values()
        )
        return RunSummary(
            run_id=run_id,
            workflow_id=workflow.id,
            product_id=product.id,
            listing_version_id=listing.id if listing is not None else None,
            product_title=product.working_title,
            execution_mode=selected_run.execution_mode,
            fixture_completed=(
                selected_run.execution_mode == "fixture" and workflow.completed_at is not None
            ),
            workflow_completed=workflow.completed_at is not None,
            pending_effects=pending_effects,
            completed_at=workflow.completed_at,
            product_state=workflow.product_state,
            jobs=[ProofJob(id=job.id, job_type=job.job_type, status=job.status) for job in jobs],
            recoveries=_recovery_proofs(product.id, jobs, runs, list(latest_effects.values())),
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
        selected_run = await select_operator_run(session, run_id)
        row = (
            await session.execute(
                _artifact_query(selected_run).where(Artifact.id == artifact_id).limit(1)
            )
        ).first()
    except (SQLAlchemyError, OSError) as error:
        raise HTTPException(status_code=503, detail="operator database unavailable") from error
    if row is None:
        raise HTTPException(status_code=404, detail="fixture artifact not found")
    artifact, asset = row
    try:
        content = await asyncio.to_thread(_verified_bytes, artifact, run_id)
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
