"""Typed deterministic creative-asset handler contracts."""

from pathlib import Path
from typing import Literal

from money_machine.domain.models.listing import ListingPackage
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.value_objects import FrozenModel


class CreativeAssetRequest(FrozenModel):
    package: ListingPackage
    spec: ProductSpec
    build: BuildResult
    qa: ProductQAResult
    destination: Path
    database_url: str


class CreativeAssetResponse(FrozenModel):
    package: ListingPackage
    event_name: Literal["ASSET_QA_PASSED"] = "ASSET_QA_PASSED"
    successor_job_type: Literal["RUN_PREFLIGHT"] = "RUN_PREFLIGHT"
