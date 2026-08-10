"""Read-only workflow job route."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from money_machine.api.dependencies import get_unit_of_work
from money_machine.api.schemas import JobResponse
from money_machine.persistence.unit_of_work import UnitOfWork

router = APIRouter(prefix="/workflows", tags=["jobs"])


@router.get("/{workflow_run_id}/jobs", response_model=tuple[JobResponse, ...])
async def list_jobs(
    workflow_run_id: UUID,
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> tuple[JobResponse, ...]:
    if await uow.workflows.get(workflow_run_id) is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    jobs = await uow.jobs.list_for_workflow(workflow_run_id)
    return tuple(
        JobResponse(
            job_id=job.job_id,
            job_type=job.job_type,
            state=job.state.value,
            retry_class=job.retry_class.value,
            max_attempts=job.max_attempts,
        )
        for job in jobs
    )
