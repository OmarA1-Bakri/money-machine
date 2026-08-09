"""Deterministic normalized catalogue deduplication."""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Sequence

from money_machine.domain.models.product_spec import DedupeResult, ProductSpec
from money_machine.domain.services.low_ticket import normalize_concept
from money_machine.domain.value_objects import FrozenModel, canonical_sha256

_DEFAULT_STOP_WORDS = frozenset({"a", "an", "and", "for", "of", "the", "to", "with"})


def title_tokens(value: str, stop_words: Iterable[str] = _DEFAULT_STOP_WORDS) -> frozenset[str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    excluded = {word.casefold() for word in stop_words}
    punctuation_separated = "".join(
        " " if unicodedata.category(character).startswith("P") else character
        for character in normalized
    )
    return frozenset(token for token in punctuation_separated.split() if token not in excluded)


def title_token_overlap(left: str, right: str, stop_words: Iterable[str]) -> float:
    left_tokens = title_tokens(left, stop_words)
    right_tokens = title_tokens(right, stop_words)
    denominator = min(len(left_tokens), len(right_tokens))
    return 0.0 if denominator == 0 else len(left_tokens & right_tokens) / denominator


def product_title(spec: ProductSpec) -> str:
    """Derive the only canonical title available in the frozen ProductSpec contract."""

    return f"{spec.identity_niche} {spec.base_category}"


class _DedupeBody(FrozenModel):
    product_spec_id: str
    passed: bool
    matched_product_spec_ids: tuple[str, ...]
    reasons: tuple[str, ...]


class DedupeService:
    """Compare one specification with a local catalogue without mutating it."""

    def __init__(self, *, stop_words: Iterable[str] = _DEFAULT_STOP_WORDS) -> None:
        self._stop_words = frozenset(word.casefold() for word in stop_words)

    def evaluate(self, spec: ProductSpec, catalogue: Sequence[ProductSpec]) -> DedupeResult:
        matches: list[str] = []
        reasons: list[str] = []
        compared: list[str] = []
        for existing in sorted(catalogue, key=lambda item: item.product_spec_id):
            if existing.product_spec_id == spec.product_spec_id:
                raise ValueError("catalogue cannot contain the candidate product_spec_id")
            compared.append(existing.product_spec_id)
            exact = normalize_concept(existing.identity_niche) == normalize_concept(
                spec.identity_niche
            ) and normalize_concept(existing.base_category) == normalize_concept(spec.base_category)
            overlap = title_token_overlap(
                product_title(spec), product_title(existing), self._stop_words
            )
            if exact or overlap >= 0.70:
                matches.append(existing.product_spec_id)
                if exact and "identity_category_match" not in reasons:
                    reasons.append("identity_category_match")
                overlap_reason = f"title_token_overlap:{overlap:.3f}"
                if overlap >= 0.70 and overlap_reason not in reasons:
                    reasons.append(overlap_reason)

        passed = not matches
        if passed:
            reasons = [f"compared:{item}" for item in compared] or ["catalogue_empty"]
        body = _DedupeBody(
            product_spec_id=spec.product_spec_id,
            passed=passed,
            matched_product_spec_ids=tuple(matches),
            reasons=tuple(reasons),
        )
        digest = canonical_sha256(body)
        return DedupeResult(
            dedupe_result_id=f"DD-{digest[:24]}",
            result_sha256=digest,
            **body.model_dump(exclude={"schema_version"}),
        )


__all__ = ["DedupeService", "product_title", "title_token_overlap", "title_tokens"]
