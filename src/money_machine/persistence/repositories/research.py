"""Research run, observation and candidate access."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from money_machine.persistence.repositories._base import Repository
from money_machine.persistence.tables import (
    MarketListingObservation,
    ProductCandidate,
    ResearchRun,
)


class ResearchRunRepository(Repository[ResearchRun]):
    """Market-research collections and their row counts."""

    model = ResearchRun

    async def for_workflow(self, workflow_id: UUID) -> tuple[ResearchRun, ...]:
        """Every research run in one workflow."""
        statement = (
            select(ResearchRun)
            .where(ResearchRun.workflow_id == workflow_id)
            .order_by(ResearchRun.created_at)
        )
        return tuple((await self.session.execute(statement)).scalars().all())

    async def observations(self, research_run_id: UUID) -> tuple[MarketListingObservation, ...]:
        """Listing observations collected by one research run."""
        statement = select(MarketListingObservation).where(
            MarketListingObservation.research_run_id == research_run_id
        )
        return tuple((await self.session.execute(statement)).scalars().all())


class ProductCandidateRepository(Repository[ProductCandidate]):
    """Shortlisted candidates and their Low-Ticket scores."""

    model = ProductCandidate

    async def shortlist(self, workflow_id: UUID) -> tuple[ProductCandidate, ...]:
        """The shortlist for one workflow, highest score first."""
        statement = (
            select(ProductCandidate)
            .where(ProductCandidate.workflow_id == workflow_id)
            .order_by(ProductCandidate.total_score.desc().nullslast())
        )
        return tuple((await self.session.execute(statement)).scalars().all())
