"""Playbook shape rules bound into contracts so a malformed package cannot exist.

The numeric values live in ``config/product_rules.yaml`` (typed by
``money_machine.config.settings``); these value objects carry them into the domain so that
``ListingPackage`` and ``ProductSpec`` validate against the configured playbook shape at
construction time and record which rule version they satisfied.
"""

from typing import Self

from pydantic import model_validator

from money_machine.domain.models._base import ContractModel, NonEmptyStr, PositiveInt


class ListingRules(ContractModel):
    """Exact listing-package shape required by the playbook (workbook §7, listing package)."""

    rule_version: NonEmptyStr
    tags: PositiveInt
    images: PositiveInt
    videos: PositiveInt
    description_sections: PositiveInt
    quantity: PositiveInt
    image_role: NonEmptyStr
    video_role: NonEmptyStr

    @model_validator(mode="after")
    def validate_roles(self) -> Self:
        if self.image_role.casefold() == self.video_role.casefold():
            raise ValueError("image and video artifact roles must differ")
        return self


class ProductShapeRules(ContractModel):
    """Inclusive hub and colour-variant ranges required by the playbook (workbook §7)."""

    rule_version: NonEmptyStr
    hubs_minimum: PositiveInt
    hubs_maximum: PositiveInt
    colour_variants_minimum: PositiveInt
    colour_variants_maximum: PositiveInt

    @model_validator(mode="after")
    def validate_ranges(self) -> Self:
        if self.hubs_minimum > self.hubs_maximum:
            raise ValueError("hubs minimum cannot exceed maximum")
        if self.colour_variants_minimum > self.colour_variants_maximum:
            raise ValueError("colour variants minimum cannot exceed maximum")
        return self
