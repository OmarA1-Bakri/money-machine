"""Frozen product specification and dedupe contracts."""

from collections import Counter
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from money_machine.domain.value_objects import FrozenModel, NonEmptyStr, Sha256

ProductFactCategory = Literal[
    "HUB_INVENTORY",
    "FEATURE",
    "COLOUR_VARIANTS",
    "BUYER_FIT",
    "WORKFLOW_OUTCOME",
]


class ProductFact(FrozenModel):
    """One exact buyer-facing fact with upstream-assigned evidence lineage."""

    claim: NonEmptyStr
    category: ProductFactCategory
    evidence_ids: Annotated[tuple[NonEmptyStr, ...], Field(min_length=1)]

    @model_validator(mode="after")
    def validate_evidence_identity(self) -> Self:
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("product fact evidence IDs must be unique")
        return self


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
    product_facts: Annotated[tuple[ProductFact, ...], Field(min_length=1)]
    source_evidence_ids: Annotated[tuple[NonEmptyStr, ...], Field(min_length=1)]
    spec_sha256: Sha256

    @model_validator(mode="after")
    def validate_truth_contract(self) -> Self:
        self.ensure_truth_contract()
        return self

    def ensure_truth_contract(self) -> None:
        """Reject semantic copy not produced by the exact first-slice strategy."""

        expected_buyer = f"People managing {self.identity_niche}"
        if self.target_buyer != expected_buyer:
            raise ValueError("target buyer must be derived from the admitted identity niche")
        expected_outcome = f"A structured {self.base_category} workspace"
        if self.promised_outcome != expected_outcome:
            raise ValueError("promised outcome must be derived from the admitted base category")

        if len(self.source_evidence_ids) != len(set(self.source_evidence_ids)):
            raise ValueError("source evidence IDs must be unique")
        claims = tuple(fact.claim for fact in self.product_facts)
        if len(claims) != len(set(claims)):
            raise ValueError("product fact claims must be unique")
        source_ids = set(self.source_evidence_ids)
        if any(not set(fact.evidence_ids).issubset(source_ids) for fact in self.product_facts):
            raise ValueError("product fact evidence must belong to ProductSpec source evidence")
        if set().union(*(set(fact.evidence_ids) for fact in self.product_facts)) != source_ids:
            raise ValueError("every ProductSpec source evidence ID must support a product fact")

        semantic_facts = {
            fact.category: fact.claim
            for fact in self.product_facts
            if fact.category in {"BUYER_FIT", "WORKFLOW_OUTCOME"}
        }
        if semantic_facts.get("BUYER_FIT") != self.target_buyer:
            raise ValueError("target buyer must have one exact typed product fact")
        if semantic_facts.get("WORKFLOW_OUTCOME") != self.promised_outcome:
            raise ValueError("promised outcome must have one exact typed product fact")
        if sum(fact.category == "BUYER_FIT" for fact in self.product_facts) != 1:
            raise ValueError("ProductSpec must contain exactly one buyer-fit fact")
        if sum(fact.category == "WORKFLOW_OUTCOME" for fact in self.product_facts) != 1:
            raise ValueError("ProductSpec must contain exactly one workflow-outcome fact")

        expected_facts = Counter(
            (
                ("HUB_INVENTORY", f"Configured with {len(self.hubs)} hubs"),
                *(("FEATURE", f"Includes {feature}") for feature in self.features),
                (
                    "COLOUR_VARIANTS",
                    f"Configured with {len(self.colour_variants)} colour variants",
                ),
                ("BUYER_FIT", self.target_buyer),
                ("WORKFLOW_OUTCOME", self.promised_outcome),
            )
        )
        actual_facts = Counter((fact.category, fact.claim) for fact in self.product_facts)
        if actual_facts != expected_facts:
            raise ValueError("product facts must exactly match the typed ProductSpec structure")


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
