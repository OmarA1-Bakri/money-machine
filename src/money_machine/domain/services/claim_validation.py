"""Deterministic, evidence-bearing validation for product-facing claims."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from typing import Literal

from pydantic import Field

from money_machine.domain.value_objects import FrozenModel, NonEmptyStr

ClaimSource = Literal["PRODUCT_FACT", "STRUCTURAL_COPY", "REJECTED"]
FactCategory = Literal[
    "HUB_INVENTORY",
    "FEATURE",
    "COLOUR_VARIANTS",
    "BUYER_FIT",
    "WORKFLOW_OUTCOME",
]


class AdmittedFact(FrozenModel):
    """A positive, typed ProductSpec fact with its local evidence lineage."""

    claim: NonEmptyStr
    category: FactCategory
    evidence_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)


class ClaimRecord(FrozenModel):
    """One stable decision from the product-fact claim ledger."""

    claim: NonEmptyStr
    normalized_claim: NonEmptyStr
    source: ClaimSource
    fact_index: int | None = None
    fact_category: FactCategory | None = None
    evidence_ids: tuple[NonEmptyStr, ...] = ()
    reason_code: str | None = None


class ClaimValidationResult(FrozenModel):
    passed: bool
    records: tuple[ClaimRecord, ...]


_SPACE = re.compile(r"\s+")


def normalize_claim(value: str) -> str:
    """Normalize matching syntax without paraphrasing or changing meaning."""

    normalized = unicodedata.normalize("NFKC", value).casefold().strip()
    normalized = normalized.replace("\N{EN DASH}", "-").replace("\N{EM DASH}", "-")
    return _SPACE.sub(" ", normalized.rstrip(".!?"))


class ClaimValidationService:
    """Accept only exact, typed facts or caller-enumerated structural copy."""

    def validate(
        self,
        claims: Sequence[str],
        product_facts: Sequence[str],
        *,
        admitted_facts: Sequence[AdmittedFact] = (),
        structural_claims: Sequence[str] = (),
    ) -> ClaimValidationResult:
        normalized_facts = tuple(normalize_claim(fact) for fact in product_facts)
        normalized_structural = frozenset(normalize_claim(claim) for claim in structural_claims)
        admitted = {normalize_claim(fact.claim): fact for fact in admitted_facts}
        if not set(admitted).issubset(normalized_facts):
            raise ValueError("admitted facts must be present in ProductSpec product_facts")
        records = tuple(
            self._validate_one(claim, normalized_facts, normalized_structural, admitted)
            for claim in claims
        )
        return ClaimValidationResult(
            passed=all(record.source != "REJECTED" for record in records),
            records=records,
        )

    @staticmethod
    def _validate_one(
        claim: str,
        normalized_facts: tuple[str, ...],
        normalized_structural: frozenset[str],
        admitted: dict[str, AdmittedFact],
    ) -> ClaimRecord:
        normalized = normalize_claim(claim)
        if not normalized:
            raise ValueError("claims must not be empty")
        if normalized in normalized_structural:
            return ClaimRecord(
                claim=claim,
                normalized_claim=normalized,
                source="STRUCTURAL_COPY",
            )
        fact = admitted.get(normalized)
        if fact is not None:
            return ClaimRecord(
                claim=claim,
                normalized_claim=normalized,
                source="PRODUCT_FACT",
                fact_index=normalized_facts.index(normalized),
                fact_category=fact.category,
                evidence_ids=fact.evidence_ids,
            )
        return ClaimRecord(
            claim=claim,
            normalized_claim=normalized,
            source="REJECTED",
            reason_code=(
                "UNADMITTED_PRODUCT_FACT"
                if normalized in normalized_facts
                else "UNBOUND_PRODUCT_CLAIM"
            ),
        )
