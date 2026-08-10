"""Contract for the QUALIFY_CANDIDATES research handler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from money_machine.domain.enums import ProductState
from money_machine.domain.events import DomainEventName
from money_machine.domain.models.candidate import CandidateShortlist, QualificationScore


class MarketResearchRepository(Protocol):
    async def load_predecessor_result[Result](
        self, job_id: UUID, result_type: type[Result]
    ) -> Result: ...

    async def persist_qualification(
        self,
        packet_id: str,
        scores: tuple[QualificationScore, ...],
        shortlist: CandidateShortlist | None,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class MarketResearchOutcome:
    result: CandidateShortlist | None
    scores: tuple[QualificationScore, ...]
    event_name: DomainEventName | None
    terminal_state: ProductState | None
    next_job_type: Literal["CREATE_PRODUCT_SPEC"] | None


__all__ = ["MarketResearchOutcome", "MarketResearchRepository"]
