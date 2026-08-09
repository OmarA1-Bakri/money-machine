"""Contract for the CREATE_PRODUCT_SPEC research handler."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from money_machine.domain.events import DomainEventName
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.models.research import ResearchPacket


class ProductStrategyRepository(Protocol):
    async def load_predecessor_result[Result](
        self, job_id: UUID, result_type: type[Result]
    ) -> Result: ...

    async def load_packet(self, packet_id: str) -> ResearchPacket: ...


@dataclass(frozen=True, slots=True)
class ProductStrategyOutcome:
    result: ProductSpec
    event_name: DomainEventName


__all__ = ["ProductStrategyOutcome", "ProductStrategyRepository"]
