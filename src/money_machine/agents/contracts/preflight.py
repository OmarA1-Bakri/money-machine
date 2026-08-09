"""Typed fail-closed preflight handler contracts."""

from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import AwareDatetime

from money_machine.domain.models.listing import ListingPackage, PreflightResult
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.value_objects import FrozenModel


class PreflightRequest(FrozenModel):
    package: ListingPackage
    qa: ProductQAResult
    spec: ProductSpec
    build: BuildResult
    artifact_root: Path
    database_url: str
    checked_at: AwareDatetime
    external_effect_mode: str = "simulation"
    incremental_spend: Decimal | None = Decimal("0.00")
    publication_receipt_present: bool = False


class PreflightResponse(FrozenModel):
    result: PreflightResult
    event_name: Literal["DRAFT_READY", "REPAIR_REQUIRED", "BLOCKED"]
    successor_job_type: Literal["REPAIR_LISTING_PACKAGE"] | None
