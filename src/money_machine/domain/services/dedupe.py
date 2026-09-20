"""Catalogue dedupe service implementing D-0013 rules.

Deterministic dedupe logic:
1. Exact identity + category match → EXACT_IDENTITY_CATEGORY collision
2. Title similarity (Jaccard >= 0.70) → TITLE_SIMILARITY collision
3. Concept fingerprint match → CONCEPT_FINGERPRINT collision

Returns PASS (requires differentiation evidence against non-empty catalogue)
or TOO_CLOSE (requires collision evidence).
"""

import re
import unicodedata
from typing import Final
from uuid import UUID

from money_machine.domain.enums import BranchOutcome
from money_machine.domain.models.common import EvidenceReference
from money_machine.domain.models.products import DedupeCollision, DedupeResult, ProductSpec

JACCARD_THRESHOLD: Final[float] = 0.70
"""D-0013: Configured Jaccard threshold for title similarity."""


def normalize_title(title: str) -> str:
    """Normalize title for similarity comparison per D-0013.

    Steps:
    1. Unicode normalize (NFKD)
    2. Case-fold (lowercase)
    3. Strip punctuation
    4. Collapse whitespace
    5. Trim

    Args:
        title: Raw product title

    Returns:
        Normalized title string
    """
    # Unicode normalize
    normalized = unicodedata.normalize("NFKD", title)
    # Case-fold
    normalized = normalized.casefold()
    # Strip punctuation (keep alphanumeric and spaces)
    normalized = re.sub(r"[^\w\s]", "", normalized)
    # Collapse whitespace
    normalized = re.sub(r"\s+", " ", normalized)
    # Trim
    return normalized.strip()


def tokenize_title(normalized_title: str) -> set[str]:
    """Tokenize normalized title into word set.

    Args:
        normalized_title: Output from normalize_title()

    Returns:
        Set of unique tokens (words)
    """
    if not normalized_title:
        return set()
    return set(normalized_title.split())


def calculate_jaccard_similarity(tokens_a: set[str], tokens_b: set[str]) -> float:
    """Calculate Jaccard similarity between two token sets.

    Jaccard = |intersection| / |union|

    Args:
        tokens_a: First token set
        tokens_b: Second token set

    Returns:
        Jaccard similarity score (0.0 to 1.0)
    """
    if not tokens_a and not tokens_b:
        return 1.0
    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b

    if not union:
        return 0.0

    return len(intersection) / len(union)


def check_dedupe(
    candidate_spec: ProductSpec,
    existing_specs: list[ProductSpec],
    rule_version: str,
) -> DedupeResult:
    """Check if candidate ProductSpec conflicts with existing catalogue.

    Implements D-0013 dedupe rules:
    1. Matching normalized identity and base category → EXACT_IDENTITY_CATEGORY (always fails)
    2. Title Jaccard >= 0.70 → TITLE_SIMILARITY (fails)
    3. Matching concept fingerprint → CONCEPT_FINGERPRINT (fails)

    Returns PASS if no collisions (requires differentiation evidence against non-empty catalogue)
    or TOO_CLOSE if any collision found.

    Args:
        candidate_spec: ProductSpec to check for collisions
        existing_specs: List of existing ProductSpecs in catalogue
        rule_version: Dedupe rule version identifier

    Returns:
        DedupeResult with PASS or TOO_CLOSE outcome
    """
    collisions: list[DedupeCollision] = []
    compared_spec_ids: list[UUID] = []

    # Normalize candidate title
    candidate_normalized = normalize_title(candidate_spec.title)
    candidate_tokens = tokenize_title(candidate_normalized)
    candidate_identity_norm = candidate_spec.identity.casefold().strip()
    candidate_category_norm = candidate_spec.base_category.casefold().strip()

    # Check each existing spec
    for existing_spec in existing_specs:
        # Skip self-comparison (shouldn't happen but be safe)
        if existing_spec.spec_id == candidate_spec.spec_id:
            continue

        compared_spec_ids.append(existing_spec.spec_id)

        # Rule 1: Exact identity + category match
        existing_identity_norm = existing_spec.identity.casefold().strip()
        existing_category_norm = existing_spec.base_category.casefold().strip()

        if (
            candidate_identity_norm == existing_identity_norm
            and candidate_category_norm == existing_category_norm
        ):
            collisions.append(
                DedupeCollision(
                    other_spec_id=existing_spec.spec_id,
                    reason="EXACT_IDENTITY_CATEGORY",
                    similarity=1.0,
                    evidence=(
                        EvidenceReference(
                            evidence_id=candidate_spec.spec_id,
                            evidence_kind="SPEC_IDENTITY_CATEGORY",
                            reference=(
                                f"identity={candidate_spec.identity}, "
                                f"category={candidate_spec.base_category}"
                            ),
                        ),
                    ),
                )
            )
            continue  # No need to check other rules for this spec

        # Rule 2: Title similarity (Jaccard >= threshold)
        existing_normalized = normalize_title(existing_spec.title)
        existing_tokens = tokenize_title(existing_normalized)
        similarity = calculate_jaccard_similarity(candidate_tokens, existing_tokens)

        if similarity >= JACCARD_THRESHOLD:
            collisions.append(
                DedupeCollision(
                    other_spec_id=existing_spec.spec_id,
                    reason="TITLE_SIMILARITY",
                    similarity=similarity,
                    evidence=(
                        EvidenceReference(
                            evidence_id=candidate_spec.spec_id,
                            evidence_kind="TITLE_TOKENS",
                            reference=(
                                f"candidate={candidate_normalized}, "
                                f"existing={existing_normalized}, "
                                f"jaccard={similarity:.3f}"
                            ),
                        ),
                    ),
                )
            )
            continue

        # Rule 3: Concept fingerprint match
        if candidate_spec.concept_fingerprint == existing_spec.concept_fingerprint:
            collisions.append(
                DedupeCollision(
                    other_spec_id=existing_spec.spec_id,
                    reason="CONCEPT_FINGERPRINT",
                    similarity=1.0,
                    evidence=(
                        EvidenceReference(
                            evidence_id=candidate_spec.spec_id,
                            evidence_kind="CONCEPT_FINGERPRINT",
                            reference=f"fingerprint={candidate_spec.concept_fingerprint}",
                        ),
                    ),
                )
            )

    # Determine outcome
    if collisions:
        # TOO_CLOSE: has collisions, no differentiation
        outcome = BranchOutcome.TOO_CLOSE
        differentiation_evidence: tuple[str, ...] = ()
    else:
        # PASS: no collisions
        outcome = BranchOutcome.PASS
        # If comparing against non-empty catalogue, require differentiation evidence (D-0013)
        if existing_specs:
            differentiation_evidence = (
                f"Identity: {candidate_spec.identity}",
                f"Category: {candidate_spec.base_category}",
                f"Buyer problem: {candidate_spec.buyer_problem}",
                f"Features: {len(candidate_spec.features)} unique features",
                f"Hubs: {len(candidate_spec.hubs)} unique hubs",
            )
        else:
            # Empty catalogue: no differentiation evidence needed
            differentiation_evidence = ()

    return DedupeResult(
        result_id=candidate_spec.spec_id,  # Reuse spec_id for result_id (could be separate UUID)
        workflow_id=candidate_spec.workflow_id,
        spec_id=candidate_spec.spec_id,
        outcome=outcome,
        rule_version=rule_version,
        normalized_title=candidate_normalized,
        concept_fingerprint=candidate_spec.concept_fingerprint,
        title_similarity_threshold=JACCARD_THRESHOLD,
        compared_spec_ids=tuple(compared_spec_ids),
        collisions=tuple(collisions),
        differentiation_evidence=differentiation_evidence,
        completed_at=candidate_spec.created_at,  # Use spec creation time for now
    )
