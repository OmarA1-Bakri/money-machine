"""Contract for the CHECK_CATALOGUE_DEDUPE research handler."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from money_machine.domain.events import DomainEventName
from money_machine.domain.models.product_spec import DedupeResult, ProductSpec


class CatalogueDedupeRepository(Protocol):
    async def load_predecessor_result[Result](
        self, job_id: UUID, result_type: type[Result]
    ) -> Result: ...

    async def load_catalogue(self) -> Sequence[ProductSpec]: ...


@dataclass(frozen=True, slots=True)
class CatalogueDedupeOutcome:
    result: DedupeResult
    event_name: DomainEventName


__all__ = ["CatalogueDedupeOutcome", "CatalogueDedupeRepository"]
