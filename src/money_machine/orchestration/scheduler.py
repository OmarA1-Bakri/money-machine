"""Bounded first-product scheduler with an explicit due record."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from money_machine.orchestration.engine import OrchestrationEngine
from money_machine.orchestration.idempotency import workflow_identity
from money_machine.persistence.database import Database
from money_machine.persistence.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class ScheduleRecord:
    packet_id: str
    due_at: datetime
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.packet_id.strip():
            raise ValueError("packet_id must not be empty")
        if self.due_at.tzinfo is None or self.due_at.utcoffset() is None:
            raise ValueError("due_at must be timezone-aware")


class Scheduler:
    def __init__(self, database: Database, *, schedule: ScheduleRecord | None) -> None:
        self._database = database
        self._schedule = schedule

    async def enqueue_due(self, now: datetime) -> int:
        schedule = self._schedule
        if schedule is None or not schedule.enabled or schedule.due_at > now:
            return 0
        workflow_id = workflow_identity(schedule.packet_id.strip())
        async with UnitOfWork(self._database) as uow:
            if await uow.workflows.get(workflow_id) is not None:
                return 0
        if (
            await OrchestrationEngine(self._database).start_first_product(schedule.packet_id)
            != workflow_id
        ):
            return 0
        return 1


def main() -> int:
    """No implicit schedule: idle is a successful, effect-free process result."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger(__name__).info("scheduler idle: no explicit schedule record")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
