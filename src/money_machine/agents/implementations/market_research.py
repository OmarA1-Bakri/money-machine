"""SCORE_AND_SHORTLIST fixture/local handler."""

from money_machine.agents.contracts.market_research import (
    MarketResearchOutcome,
    MarketResearchRepository,
)
from money_machine.domain.enums import ProductState
from money_machine.domain.events import DomainEventName
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.research import ResearchPacket
from money_machine.domain.services.low_ticket import QualificationService


class MarketResearchHandler:
    def __init__(
        self,
        repository: MarketResearchRepository,
        service: QualificationService | None = None,
    ) -> None:
        self._repository = repository
        self._service = service or QualificationService()

    async def handle(self, job: JobEnvelope) -> MarketResearchOutcome:
        if job.job_type != "SCORE_AND_SHORTLIST":
            raise ValueError("market research handler received an undeclared job type")
        packet = await self._repository.load_predecessor_result(job.job_id, ResearchPacket)
        scores = self._service.score(packet)
        shortlist = self._service.shortlist(packet, scores)
        insufficient = shortlist.selected_candidate_id is None
        result = None if insufficient else shortlist
        await self._repository.persist_qualification(packet.packet_id, scores, result)
        return MarketResearchOutcome(
            result=result,
            scores=scores,
            event_name=None if insufficient else DomainEventName.CANDIDATE_SHORTLISTED,
            terminal_state=ProductState.INSUFFICIENT_EVIDENCE if insufficient else None,
            next_job_type=None if insufficient else "CREATE_PRODUCT_SPEC",
        )


__all__ = ["MarketResearchHandler"]
