"""CHECK_CATALOGUE_DEDUPE fixture/local handler."""

from money_machine.agents.contracts.catalogue_dedupe import (
    CatalogueDedupeOutcome,
    CatalogueDedupeRepository,
)
from money_machine.domain.events import DomainEventName
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.services.dedupe import DedupeService


class CatalogueDedupeHandler:
    def __init__(
        self,
        repository: CatalogueDedupeRepository,
        service: DedupeService | None = None,
    ) -> None:
        self._repository = repository
        self._service = service or DedupeService()

    async def handle(self, job: JobEnvelope) -> CatalogueDedupeOutcome:
        if job.job_type != "CHECK_CATALOGUE_DEDUPE":
            raise ValueError("catalogue dedupe handler received an undeclared job type")
        spec = await self._repository.load_predecessor_result(job.job_id, ProductSpec)
        result = self._service.evaluate(spec, await self._repository.load_catalogue())
        if not result.passed:
            raise ValueError("product specification failed catalogue dedupe")
        return CatalogueDedupeOutcome(
            result=result,
            event_name=DomainEventName.DEDUPE_PASSED,
        )


__all__ = ["CatalogueDedupeHandler"]
