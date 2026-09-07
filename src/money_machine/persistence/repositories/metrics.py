"""Metrics snapshot and decision access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from money_machine.persistence.repositories._base import Repository
from money_machine.persistence.tables import Decision, MetricsSnapshot


class MetricsSnapshotRepository(Repository[MetricsSnapshot]):
    """Weekly scorecards. Only reconciled snapshots may support a decision."""

    model = MetricsSnapshot

    async def for_listing(self, listing_id: UUID) -> tuple[MetricsSnapshot, ...]:
        """Every snapshot for one listing, oldest window first."""
        statement = (
            select(MetricsSnapshot)
            .where(MetricsSnapshot.listing_id == listing_id)
            .order_by(MetricsSnapshot.window_start)
        )
        return tuple((await self.session.execute(statement)).scalars().all())

    async def reconciled_for_listing(self, listing_id: UUID) -> tuple[MetricsSnapshot, ...]:
        """Only the reconciled snapshots, which are the only valid decision input."""
        statement = (
            select(MetricsSnapshot)
            .where(MetricsSnapshot.listing_id == listing_id, MetricsSnapshot.reconciled)
            .order_by(MetricsSnapshot.window_start)
        )
        return tuple((await self.session.execute(statement)).scalars().all())


class DecisionRepository(Repository[Decision]):
    """Durable decisions with their evidence citations."""

    model = Decision

    async def for_workflow(self, workflow_id: UUID) -> tuple[Decision, ...]:
        """Every decision recorded in one workflow."""
        statement = (
            select(Decision)
            .where(Decision.workflow_id == workflow_id)
            .order_by(Decision.decided_at)
        )
        return tuple((await self.session.execute(statement)).scalars().all())
