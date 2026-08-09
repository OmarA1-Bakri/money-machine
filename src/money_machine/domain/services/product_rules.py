"""Evidence-bound deterministic product specification rules."""

from __future__ import annotations

from dataclasses import dataclass

from money_machine.config.validation import ProductRulesSection
from money_machine.domain.models.candidate import CandidateShortlist, QualificationScore
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.models.research import ResearchPacket
from money_machine.domain.services.low_ticket import (
    QualificationService,
    candidate_id_for,
    normalize_concept,
)
from money_machine.domain.value_objects import FrozenModel, canonical_sha256


@dataclass(frozen=True, slots=True)
class ProductRules:
    """Configured structural content; no marketplace claim templates are accepted."""

    hubs: tuple[str, ...]
    colour_variants: tuple[str, ...]

    def __post_init__(self) -> None:
        if not 6 <= len(self.hubs) <= 8:
            raise ValueError("product rules require 6..8 hubs")
        if not 3 <= len(self.colour_variants) <= 4:
            raise ValueError("product rules require 3..4 colour variants")
        if any(not item.strip() for item in (*self.hubs, *self.colour_variants)):
            raise ValueError("product rule labels cannot be empty")

    @classmethod
    def default(cls) -> ProductRules:
        return cls(
            hubs=("Home", "Plan", "Track", "Library", "Review", "Settings"),
            colour_variants=("Ink", "Sage", "Sand"),
        )

    @classmethod
    def from_config(cls, config: ProductRulesSection) -> ProductRules:
        default = cls.default()
        return cls(
            hubs=default.hubs[: config.min_hubs],
            colour_variants=default.colour_variants[: config.min_colour_variants],
        )


class _SpecBody(FrozenModel):
    candidate_id: str
    identity_niche: str
    base_category: str
    target_buyer: str
    promised_outcome: str
    hubs: tuple[str, ...]
    colour_variants: tuple[str, ...]
    features: tuple[str, ...]
    product_facts: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]


class ProductStrategyService:
    """Create one stable ProductSpec from admitted evidence and structural rules."""

    def create_spec(
        self,
        packet: ResearchPacket,
        shortlist: CandidateShortlist,
        selected: QualificationScore,
        rules: ProductRules,
    ) -> ProductSpec:
        shortlisted = {item.candidate_id: item for item in shortlist.candidates}
        if selected.candidate_id not in shortlisted:
            raise ValueError("selected candidate is not in shortlist")
        if not selected.meets_threshold:
            raise ValueError("selected candidate does not meet threshold")
        if shortlisted[selected.candidate_id] != selected:
            raise ValueError("selected score differs from shortlisted score")
        if shortlist.selected_candidate_id != selected.candidate_id:
            raise ValueError("selected candidate is not the shortlist decision")

        qualifier = QualificationService()
        canonical_scores = qualifier.score(packet)
        canonical_shortlist = qualifier.shortlist(packet, canonical_scores)
        if shortlist != canonical_shortlist:
            raise ValueError("shortlist differs from canonical recomputation")
        canonical_selected = next(
            (
                item
                for item in canonical_shortlist.candidates
                if item.candidate_id == canonical_shortlist.selected_candidate_id
            ),
            None,
        )
        if selected != canonical_selected:
            raise ValueError("selected score differs from canonical recomputation")

        observations = tuple(
            item
            for item in packet.observations
            if candidate_id_for(item.identity_niche, item.base_category) == selected.candidate_id
        )
        if not observations:
            raise ValueError("selected candidate has no admitted packet evidence")
        evidence_ids = tuple(sorted(item.evidence.evidence_id for item in observations))
        if evidence_ids != selected.evidence_ids:
            raise ValueError("selected score evidence differs from admitted packet evidence")

        identity_niche = normalize_concept(observations[0].identity_niche)
        base_category = normalize_concept(observations[0].base_category)
        body = _SpecBody(
            candidate_id=selected.candidate_id,
            identity_niche=identity_niche,
            base_category=base_category,
            target_buyer=f"People managing {identity_niche}",
            promised_outcome=f"A structured {base_category} workspace",
            hubs=rules.hubs,
            colour_variants=rules.colour_variants,
            features=tuple(f"{hub} hub" for hub in rules.hubs),
            product_facts=(
                f"Configured with {len(rules.hubs)} hubs",
                f"Configured with {len(rules.colour_variants)} colour variants",
                *(f"Supported by evidence {evidence_id}" for evidence_id in evidence_ids),
            ),
            source_evidence_ids=evidence_ids,
        )
        digest = canonical_sha256(body)
        return ProductSpec(
            product_spec_id=f"PS-{digest[:24]}",
            spec_sha256=digest,
            **body.model_dump(exclude={"schema_version"}),
        )


__all__ = ["ProductRules", "ProductStrategyService"]
