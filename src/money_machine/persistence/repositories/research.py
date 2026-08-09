"""Research, candidate, score, and shortlist repositories."""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.models.candidate import CandidateShortlist, QualificationScore
from money_machine.domain.models.research import (
    EvidenceReference,
    ResearchObservation,
    ResearchPacket,
)
from money_machine.domain.value_objects import canonical_sha256
from money_machine.persistence.database import JsonModelRepository
from money_machine.persistence.tables import (
    candidate_shortlists,
    candidates,
    evidence_references,
    qualification_scores,
    research_observations,
    research_packets,
)


class ResearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._packets = JsonModelRepository(session, research_packets, "packet_id", ResearchPacket)
        self._observations = JsonModelRepository(
            session, research_observations, "observation_id", ResearchObservation
        )
        self._evidence = JsonModelRepository(
            session, evidence_references, "evidence_id", EvidenceReference
        )
        self._scores = JsonModelRepository(
            session, qualification_scores, "qualification_score_id", QualificationScore
        )
        self._shortlists = JsonModelRepository(
            session, candidate_shortlists, "shortlist_id", CandidateShortlist
        )
        self._session = session

    async def add_packet(self, packet: ResearchPacket) -> None:
        await self._packets.add(packet, identity=packet.packet_id)
        for observation in packet.observations:
            await self._evidence.add(
                observation.evidence,
                identity=observation.evidence.evidence_id,
                extra_values={"packet_id": packet.packet_id},
            )
            await self._observations.add(
                observation,
                identity=observation.observation_id,
                extra_values={"packet_id": packet.packet_id},
            )

    async def get_packet(self, packet_id: str) -> ResearchPacket | None:
        return await self._packets.get(packet_id)

    async def get_evidence(self, evidence_id: str) -> EvidenceReference | None:
        return await self._evidence.get(evidence_id)

    async def add_score(self, packet_id: str, score: QualificationScore) -> None:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        existing = await self._scores.get(score.candidate_id)
        if existing is not None and existing != score:
            raise ValueError(f"identity collision for {score.candidate_id}")
        if existing is not None:
            return
        candidate_payload = {"candidate_id": score.candidate_id, "packet_id": packet_id}
        candidate_hash = canonical_sha256(candidate_payload)
        inserted_hash = (
            await self._session.execute(
                pg_insert(candidates)
                .values(
                    candidate_id=score.candidate_id,
                    packet_id=packet_id,
                    payload=candidate_payload,
                    payload_sha256=candidate_hash,
                )
                .on_conflict_do_nothing(index_elements=[candidates.c.candidate_id])
                .returning(candidates.c.payload_sha256)
            )
        ).scalar_one_or_none()
        if inserted_hash is None:
            stored_hash = await self._session.scalar(
                select(candidates.c.payload_sha256).where(
                    candidates.c.candidate_id == score.candidate_id
                )
            )
            if stored_hash != candidate_hash:
                raise ValueError(f"identity collision for {score.candidate_id}")
        await self._scores.add(
            score,
            identity=score.candidate_id,
            extra_values={"candidate_id": score.candidate_id, "score_total": score.total},
        )

    async def add_shortlist(self, shortlist: CandidateShortlist) -> None:
        await self._shortlists.add(
            shortlist,
            identity=shortlist.shortlist_id,
            extra_values={"packet_id": shortlist.packet_id},
        )

    async def get_shortlist(self, shortlist_id: str) -> CandidateShortlist | None:
        return await self._shortlists.get(shortlist_id)

    async def list_scores(self, packet_id: str) -> tuple[QualificationScore, ...]:
        payloads = (
            await self._session.execute(
                select(qualification_scores.c.payload)
                .join(
                    candidates,
                    qualification_scores.c.candidate_id == candidates.c.candidate_id,
                )
                .where(candidates.c.packet_id == packet_id)
                .order_by(qualification_scores.c.qualification_score_id)
            )
        ).scalars()
        return tuple(
            QualificationScore.model_validate_json(json.dumps(payload, separators=(",", ":")))
            for payload in payloads
        )
