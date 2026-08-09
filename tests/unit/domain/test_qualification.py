from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from money_machine.application.services.research_service import ResearchService
from money_machine.domain.models.candidate import QualificationScore
from money_machine.domain.services.low_ticket import QualificationService, candidate_id_for

NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)


def test_scores_grouped_normalized_candidates_with_half_up_medians() -> None:
    packet = ResearchService().import_packet(
        Path("tests/fixtures/research/valid_packet_30.json"), now=NOW
    )
    scores = QualificationService().score(packet)
    score = next(
        item for item in scores if item.candidate_id == candidate_id_for("Budget Moms", "Planner")
    )
    assert (score.demand, score.differentiation, score.build_feasibility, score.buyer_value) == (
        8,
        8,
        8,
        8,
    )
    assert len(score.evidence_ids) == 5


def test_shortlist_is_deterministic_and_selects_first_qualifying_candidate() -> None:
    packet = ResearchService().import_packet(
        Path("tests/fixtures/research/valid_packet_30.json"), now=NOW
    )
    service = QualificationService()
    scores = service.score(packet)
    shortlist = service.shortlist(packet, tuple(reversed(scores)))
    expected = tuple(
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
    assert shortlist.candidates == expected
    assert shortlist.selected_candidate_id == expected[0].candidate_id
    assert shortlist.shortlist_id == f"SL-{shortlist.shortlist_sha256[:24]}"


def test_round_half_up_is_not_bankers_rounding() -> None:
    assert QualificationService.round_median((Decimal("6"), Decimal("7"))) == 7


def test_shortlist_recomputes_every_score_and_rejects_forged_or_incomplete_inputs() -> None:
    packet = ResearchService().import_packet(
        Path("tests/fixtures/research/valid_packet_30.json"), now=NOW
    )
    service = QualificationService()
    scores = service.score(packet)
    forged = QualificationScore(
        candidate_id=scores[0].candidate_id,
        demand=10,
        differentiation=10,
        build_feasibility=10,
        buyer_value=10,
        evidence_ids=scores[0].evidence_ids,
    )

    with pytest.raises(ValueError, match="canonical recomputation"):
        service.shortlist(packet, (forged, *scores[1:]))
    with pytest.raises(ValueError, match="complete canonical score set"):
        service.shortlist(packet, scores[:-1])
