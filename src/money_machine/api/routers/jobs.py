"""Job list and detail. Reading a job is not claiming it."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from money_machine.api.dependencies import SessionDependency
from money_machine.api.schemas import JobPage, JobSummary
from money_machine.persistence.repositories.jobs import JobRepository
from money_machine.persistence.tables import Job

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _summary(row: Job) -> JobSummary:
    return JobSummary(
        id=row.id,
        workflow_id=row.workflow_id,
        job_type=row.job_type,
        status=row.status,
        owner_agent_id=row.owner_agent_id,
        side_effect_class=row.side_effect_class,
        retry_class=row.retry_class,
        attempt=row.attempt,
        max_attempts=row.max_attempts,
        scheduled_at=row.scheduled_at,
    )


@router.get("", response_model=JobPage)
async def list_jobs(
    session: SessionDependency,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> JobPage:
    """List durable jobs within a bounded page."""
    page = await JobRepository(session).page(limit=limit, offset=offset)
    return JobPage(
        items=tuple(_summary(row) for row in page.items),
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{job_id}", response_model=JobSummary)
async def get_job(job_id: UUID, session: SessionDependency) -> JobSummary:
    """Fetch one job."""
    row = await JobRepository(session).get(job_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found")
    return _summary(row)


@router.post("/{job_id}/retry", response_model=JobSummary)
async def retry_job(job_id: UUID, session: SessionDependency) -> JobSummary:
    """Retry a failed job."""
    from datetime import UTC, datetime

    from money_machine.orchestration.engine import retry_failed_job

    try:
        job = await retry_failed_job(
            session,
            job_id=job_id,
            now=datetime.now(UTC),
        )
        await session.commit()
        return _summary(job)
    except Exception as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry job: {error}",
        ) from error


@router.post("/{job_id}/reconcile", response_model=dict)
async def reconcile_job(
    job_id: UUID,
    session: SessionDependency,
    effect_state: str = Query(..., description="CONFIRMED or ABSENT"),
    provider_object_id: str | None = Query(None, description="Provider object ID if CONFIRMED"),
) -> dict:
    """Reconcile an uncertain external effect."""
    from datetime import UTC, datetime

    from money_machine.orchestration.engine import reconcile_uncertain_effect

    try:
        effect = await reconcile_uncertain_effect(
            session,
            job_id=job_id,
            effect_state=effect_state,
            provider_object_id=provider_object_id,
            now=datetime.now(UTC),
        )
        await session.commit()
        return {
            "id": str(effect.id),
            "effect_state": effect.effect_state,
            "provider_object_id": effect.provider_object_id,
        }
    except Exception as error:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reconcile effect: {error}",
        ) from error
