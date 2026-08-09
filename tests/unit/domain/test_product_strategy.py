from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from money_machine.application.services.research_service import ResearchService
from money_machine.domain.models.candidate import CandidateShortlist, QualificationScore
from money_machine.domain.models.research import ResearchPacket
from money_machine.domain.services.low_ticket import QualificationService
from money_machine.domain.services.product_rules import ProductRules, ProductStrategyService
from money_machine.domain.value_objects import canonical_sha256

NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)


def _inputs() -> tuple[ResearchPacket, CandidateShortlist, QualificationScore]:
    packet = ResearchService().import_packet(
        Path("tests/fixtures/research/valid_packet_30.json"), now=NOW
    )
    qualifier = QualificationService()
    shortlist = qualifier.shortlist(packet, qualifier.score(packet))
    selected = next(
        score
        for score in shortlist.candidates
        if score.candidate_id == shortlist.selected_candidate_id
    )
    return packet, shortlist, selected


def test_create_spec_is_deterministic_evidence_bound_and_recomputable() -> None:
    packet, shortlist, selected = _inputs()
    service = ProductStrategyService()
    first = service.create_spec(packet, shortlist, selected, ProductRules.default())
    second = service.create_spec(packet, shortlist, selected, ProductRules.default())
    assert first == second
    assert 6 <= len(first.hubs) <= 8
    assert 3 <= len(first.colour_variants) <= 4
    assert first.target_buyer and first.promised_outcome and first.features and first.product_facts
    assert first.source_evidence_ids == selected.evidence_ids
    body = cast(
        dict[str, object],
        first.model_dump(exclude={"product_spec_id", "spec_sha256"}),
    )
    assert first.spec_sha256 == canonical_sha256(body)
    assert first.product_spec_id == f"PS-{first.spec_sha256[:24]}"


def test_create_spec_denies_unqualified_or_non_shortlisted_candidate() -> None:
    packet, shortlist, selected = _inputs()
    service = ProductStrategyService()
    denied = selected.model_copy(update={"demand": 0})
    with pytest.raises(ValueError, match="threshold"):
        service.create_spec(packet, shortlist, denied, ProductRules.default())
    outsider = selected.model_copy(update={"candidate_id": "CAND-outsider"})
    with pytest.raises(ValueError, match="shortlist"):
        service.create_spec(packet, shortlist, outsider, ProductRules.default())


def test_create_spec_recomputes_packet_scores_and_rejects_forged_40_of_40() -> None:
    packet, shortlist, selected = _inputs()
    low_observations = tuple(
        observation.model_copy(
            update={
                "qualification_inputs": {
                    dimension: Decimal("0") for dimension in observation.qualification_inputs
                }
            }
        )
        for observation in packet.observations
    )
    low_packet = packet.model_copy(update={"observations": low_observations})
    forged = selected.model_copy(
        update={
            "demand": 10,
            "differentiation": 10,
            "build_feasibility": 10,
            "buyer_value": 10,
        }
    )
    forged_shortlist = shortlist.model_copy(
        update={"candidates": (forged, *shortlist.candidates[1:])}
    )

    with pytest.raises(ValueError, match="canonical recomputation"):
        ProductStrategyService().create_spec(
            low_packet, forged_shortlist, forged, ProductRules.default()
        )
