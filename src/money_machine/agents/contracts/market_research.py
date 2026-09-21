"""A03 Market Research Agent contract and implementation binding."""

from __future__ import annotations

from typing import TYPE_CHECKING

from money_machine.agents.implementations.market_research import MarketResearchAgent
from money_machine.domain.models.research import ResearchReport

if TYPE_CHECKING:
    from uuid import UUID

    from money_machine.persistence.tables import Job
    from money_machine.persistence.unit_of_work import UnitOfWork


async def execute_market_research(
    workflow_id: UUID,
    job: Job,
    uow: UnitOfWork,
) -> ResearchReport:
    """
    Execute A03 Market Research Agent.

    Collects 25-40 market observations from fixture adapter,
    generates shortlist of 5 identityxcategory candidates.

    Args:
        workflow_id: Workflow this research belongs to
        job: Market research job
        uow: Unit of work for persistence

    Returns:
        ResearchReport with observations and shortlist

    Raises:
        ValueError: If configuration is missing or invalid
        NotImplementedError: If non-fixture adapter is used while uncommissioned
    """
    agent = MarketResearchAgent()
    return await agent.execute(workflow_id, job, uow)
