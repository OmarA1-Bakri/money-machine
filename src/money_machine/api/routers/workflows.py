"""Read-only workflow status route."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from money_machine.api.dependencies import get_unit_of_work
from money_machine.api.schemas import BlockerResponse, WorkflowResponse
from money_machine.persistence.unit_of_work import UnitOfWork

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.get("/{workflow_run_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_run_id: UUID,
    uow: Annotated[UnitOfWork, Depends(get_unit_of_work)],
) -> WorkflowResponse:
    workflow = await uow.workflows.get(workflow_run_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow not found")
    blocker = workflow.terminal_blocker
    return WorkflowResponse(
        workflow_run_id=workflow.workflow_run_id,
        workflow_type=workflow.workflow_type,
        packet_id=workflow.packet_id,
        state=workflow.state.value,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        terminal_blocker=(
            None
            if blocker is None
            else BlockerResponse(
                code=blocker.code,
                message=blocker.message,
                result_type=blocker.result_type,
                result_id=blocker.result_id,
                result_sha256=blocker.result_sha256,
                occurred_at=blocker.occurred_at,
            )
        ),
    )
