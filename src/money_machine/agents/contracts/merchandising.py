"""Typed merchandising handler contracts."""

from typing import Literal

from money_machine.domain.models.listing import ListingPackage
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.services.claim_validation import ClaimRecord
from money_machine.domain.value_objects import FrozenModel


class MerchandisingRequest(FrozenModel):
    spec: ProductSpec
    build: BuildResult
    qa: ProductQAResult


class MerchandisingResponse(FrozenModel):
    package: ListingPackage
    claim_records: tuple[ClaimRecord, ...]
    event_name: Literal["LISTING_PACKAGE_CREATED"] = "LISTING_PACKAGE_CREATED"
    successor_job_type: Literal["RENDER_LISTING_ASSETS"] = "RENDER_LISTING_ASSETS"
