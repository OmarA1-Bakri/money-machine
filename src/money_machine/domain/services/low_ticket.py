"""Deterministic low-ticket qualification and shortlist rules."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from money_machine.domain.enums import QualificationDimension
from money_machine.domain.models.candidate import CandidateShortlist, QualificationScore
from money_machine.domain.models.research import ResearchObservation, ResearchPacket
from money_machine.domain.value_objects import FrozenModel, canonical_sha256

_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)


def normalize_concept(value: str) -> str:
    """Return the stable Unicode/case/punctuation-insensitive concept form."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(_NON_WORD.sub(" ", normalized).split())


class _CandidateIdentity(FrozenModel):
    identity_niche: str
    base_category: str


def candidate_id_for(identity_niche: str, base_category: str) -> str:
    identity = _CandidateIdentity(
        identity_niche=normalize_concept(identity_niche),
        base_category=normalize_concept(base_category),
    )
    return f"CAND-{canonical_sha256(identity)[:24]}"


class _ShortlistBody(FrozenModel):
    packet_id: str
    candidates: tuple[QualificationScore, ...]
    selected_candidate_id: str | None


class QualificationService:
    """Score every normalized concept and return a stable top-five shortlist."""

    @staticmethod
    def round_median(values: Sequence[Decimal]) -> int:
        if not values:
            raise ValueError("median requires at least one admitted value")
        ordered = sorted(values)
        middle = len(ordered) // 2
        median = (
            ordered[middle]
            if len(ordered) % 2
            else (ordered[middle - 1] + ordered[middle]) / Decimal("2")
        )
        return int(median.quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    def score(self, packet: ResearchPacket) -> tuple[QualificationScore, ...]:
        groups: dict[tuple[str, str], list[ResearchObservation]] = defaultdict(list)
        for observation in packet.observations:
            key = (
                normalize_concept(observation.identity_niche),
                normalize_concept(observation.base_category),
            )
            groups[key].append(observation)

        scores: list[QualificationScore] = []
        for (identity_niche, base_category), observations in sorted(groups.items()):
            dimensions = {
                dimension: self.round_median(
                    tuple(item.qualification_inputs[dimension] for item in observations)
                )
                for dimension in QualificationDimension
            }
            scores.append(
                QualificationScore(
                    candidate_id=candidate_id_for(identity_niche, base_category),
                    demand=dimensions[QualificationDimension.DEMAND],
                    differentiation=dimensions[QualificationDimension.DIFFERENTIATION],
                    build_feasibility=dimensions[QualificationDimension.BUILD_FEASIBILITY],
                    buyer_value=dimensions[QualificationDimension.BUYER_VALUE],
                    evidence_ids=tuple(sorted(item.evidence.evidence_id for item in observations)),
                )
            )
        return tuple(scores)

    def shortlist(
        self, packet: ResearchPacket, scores: Sequence[QualificationScore]
    ) -> CandidateShortlist:
        if not scores:
            raise ValueError("shortlist requires persisted qualification scores")
        if len({score.candidate_id for score in scores}) != len(scores):
            raise ValueError("qualification scores contain duplicate candidate identities")
        canonical_scores = self.score(packet)
        if len(scores) != len(canonical_scores):
            raise ValueError("shortlist requires the complete canonical score set")
        supplied_by_candidate = {score.candidate_id: score for score in scores}
        canonical_by_candidate = {score.candidate_id: score for score in canonical_scores}
        if supplied_by_candidate != canonical_by_candidate:
            raise ValueError("qualification scores differ from canonical recomputation")
        ordered = tuple(
            sorted(
                scores,
                key=lambda item: (
                    -item.total,
                    -len(item.evidence_ids),
                    -item.build_feasibility,
                    item.candidate_id,
                ),
            )[:5]
        )
        selected = next((item.candidate_id for item in ordered if item.meets_threshold), None)
        body = _ShortlistBody(
            packet_id=packet.packet_id,
            candidates=ordered,
            selected_candidate_id=selected,
        )
        digest = canonical_sha256(body)
        return CandidateShortlist(
            shortlist_id=f"SL-{digest[:24]}",
            packet_id=packet.packet_id,
            candidates=ordered,
            selected_candidate_id=selected,
            shortlist_sha256=digest,
        )


__all__ = ["QualificationService", "candidate_id_for", "normalize_concept"]
