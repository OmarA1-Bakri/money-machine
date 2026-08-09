"""CREATE_PRODUCT_SPEC fixture/local handler."""

from money_machine.agents.contracts.product_strategy import (
    ProductStrategyOutcome,
    ProductStrategyRepository,
)
from money_machine.domain.events import DomainEventName
from money_machine.domain.models.candidate import CandidateShortlist
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.services.product_rules import ProductRules, ProductStrategyService


class ProductStrategyHandler:
    def __init__(
        self,
        repository: ProductStrategyRepository,
        rules: ProductRules,
        service: ProductStrategyService | None = None,
    ) -> None:
        self._repository = repository
        self._rules = rules
        self._service = service or ProductStrategyService()

    async def handle(self, job: JobEnvelope) -> ProductStrategyOutcome:
        if job.job_type != "CREATE_PRODUCT_SPEC":
            raise ValueError("product strategy handler received an undeclared job type")
        shortlist = await self._repository.load_predecessor_result(job.job_id, CandidateShortlist)
        if shortlist.selected_candidate_id is None:
            raise ValueError("shortlist is terminal INSUFFICIENT_EVIDENCE")
        selected = next(
            item
            for item in shortlist.candidates
            if item.candidate_id == shortlist.selected_candidate_id
        )
        packet = await self._repository.load_packet(shortlist.packet_id)
        return ProductStrategyOutcome(
            result=self._service.create_spec(packet, shortlist, selected, self._rules),
            event_name=DomainEventName.PRODUCT_SPEC_CREATED,
        )


__all__ = ["ProductStrategyHandler"]
