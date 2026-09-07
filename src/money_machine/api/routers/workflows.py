"""Workflow list and detail."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from money_machine.api.dependencies import SessionDependency
from money_machine.api.schemas import WorkflowPage, WorkflowSummary
from money_machine.persistence.repositories.workflows import WorkflowRunRepository
from money_machine.persistence.tables import WorkflowRun

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _summary(row: WorkflowRun) -> WorkflowSummary:
    return WorkflowSummary(
        id=row.id,
        workflow_type=row.workflow_type,
        workflow_version=row.workflow_version,
        product_state=row.product_state,
        parent_workflow_id=row.parent_workflow_id,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


@router.get("", response_model=WorkflowPage)
async def list_workflows(
    session: SessionDependency,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> WorkflowPage:
    """List durable workflows, newest state first within a bounded page."""
    page = await WorkflowRunRepository(session).page(limit=limit, offset=offset)
    return WorkflowPage(
        items=tuple(_summary(row) for row in page.items),
        total=page.total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{workflow_id}", response_model=WorkflowSummary)
async def get_workflow(workflow_id: UUID, session: SessionDependency) -> WorkflowSummary:
    """Fetch one workflow."""
    row = await WorkflowRunRepository(session).get(workflow_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="workflow not found")
    return _summary(row)
