"""Workflow-run access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from money_machine.domain.enums import ProductLifecycleState
from money_machine.persistence.repositories._base import VersionedRepository
from money_machine.persistence.tables import WorkflowRun


class WorkflowRunRepository(VersionedRepository[WorkflowRun]):
    """Durable workflow runs and their product lifecycle state."""

    model = WorkflowRun

    async def in_state(self, state: ProductLifecycleState) -> tuple[WorkflowRun, ...]:
        """Every workflow currently in one lifecycle state."""
        statement = (
            select(WorkflowRun)
            .where(WorkflowRun.product_state == state.value)
            .order_by(WorkflowRun.started_at)
        )
        return tuple((await self.session.execute(statement)).scalars().all())

    async def successors_of(self, workflow_id: UUID) -> tuple[WorkflowRun, ...]:
        """Workflows spawned from one parent by a MULTIPLY decision."""
        statement = select(WorkflowRun).where(WorkflowRun.parent_workflow_id == workflow_id)
        return tuple((await self.session.execute(statement)).scalars().all())
