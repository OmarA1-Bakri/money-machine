"""Merchandising handler implementation."""

from money_machine.agents.contracts.merchandising import (
    MerchandisingRequest,
    MerchandisingResponse,
)
from money_machine.application.services.listing_service import (
    ListingService,
    listing_claim_records,
)


def handle_merchandising(request: MerchandisingRequest) -> MerchandisingResponse:
    package = ListingService().create(request.spec, request.build, request.qa)
    claim_records = listing_claim_records(request.spec, package)
    return MerchandisingResponse(package=package, claim_records=claim_records)
