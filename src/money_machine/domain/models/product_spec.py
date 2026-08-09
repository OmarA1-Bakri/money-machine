"""Frozen product specification and dedupe contracts."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from money_machine.domain.value_objects import FrozenModel, NonEmptyStr, Sha256


class ProductSpec(FrozenModel):
    """Evidence-bound specification consumed by every downstream builder."""

    product_spec_id: NonEmptyStr
    candidate_id: NonEmptyStr
    identity_niche: NonEmptyStr
    base_category: NonEmptyStr
    target_buyer: NonEmptyStr
    promised_outcome: NonEmptyStr
    hubs: Annotated[tuple[str, ...], Field(min_length=6, max_length=8)]
    colour_variants: Annotated[tuple[str, ...], Field(min_length=3, max_length=4)]
    features: tuple[str, ...]
    product_facts: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    spec_sha256: Sha256


class DedupeResult(FrozenModel):
    """Deterministic catalogue-dedupe decision for a specification."""

    dedupe_result_id: NonEmptyStr
    product_spec_id: NonEmptyStr
    passed: bool
    matched_product_spec_ids: tuple[str, ...]
    reasons: tuple[str, ...]
    result_sha256: Sha256

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        """A passing dedupe result cannot identify a collision."""

        if self.passed and self.matched_product_spec_ids:
            raise ValueError("passed dedupe result cannot contain matches")
        return self
