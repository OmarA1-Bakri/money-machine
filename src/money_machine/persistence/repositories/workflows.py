"""Workflow run persistence."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.models.workflow import WorkflowRun
from money_machine.persistence.database import JsonModelRepository
from money_machine.persistence.tables import workflow_runs


class WorkflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._models = JsonModelRepository(session, workflow_runs, "workflow_run_id", WorkflowRun)

    async def add(self, workflow: WorkflowRun) -> None:
        await self._models.add(
            workflow,
            identity=workflow.workflow_run_id,
            extra_values={
                "workflow_type": workflow.workflow_type,
                "packet_id": workflow.packet_id,
                "state": workflow.state.value,
                "idempotency_key": workflow.idempotency_key,
                "created_at": workflow.created_at,
                "updated_at": workflow.updated_at,
            },
        )

    async def get(self, workflow_run_id: UUID) -> WorkflowRun | None:
        return await self._models.get(workflow_run_id)
