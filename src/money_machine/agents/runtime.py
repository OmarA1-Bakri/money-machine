"""Single durable runtime container for the first-product vertical slice."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from money_machine.agents.registry import FirstProductHandlers
from money_machine.application.services.product_service import ProductService
from money_machine.config.loader import load_first_product_config
from money_machine.domain.services.product_rules import ProductRules
from money_machine.integrations.notion.fixture_adapter import LocalNotionAdapter
from money_machine.orchestration.engine import OrchestrationEngine
from money_machine.orchestration.worker import Worker, WorkerResult
from money_machine.persistence.database import Database


class FirstProductRuntime:
    """Own the one engine, exact handler registry, and bounded local worker."""

    def __init__(
        self,
        database: Database,
        *,
        artifact_root: Path,
        config_root: Path,
        worker_id: str,
        clock: Callable[[], datetime] | None = None,
        lease_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id must not be empty")
        self._database = database
        self._artifact_root = artifact_root.resolve()
        self._artifact_root.mkdir(parents=True, exist_ok=True)
        self._clock = clock or (lambda: datetime.now(UTC))
        config = load_first_product_config(config_root)
        if config.product_rules.safety.external_mutations_enabled:
            raise ValueError("first-product runtime forbids external mutations")
        if config.product_rules.safety.spend_enabled:
            raise ValueError("first-product runtime forbids spend")
        product_service = ProductService(
            self._artifact_root,
            LocalNotionAdapter(),
            clock=self._clock,
        )
        handlers = FirstProductHandlers(
            database,
            artifact_root=self._artifact_root,
            product_rules=ProductRules.from_config(config.product_rules.product),
            product_service=product_service,
            clock=self._clock,
        ).registry()
        self._engine = OrchestrationEngine(database)
        self._worker = Worker(
            database,
            worker_id=worker_id.strip(),
            handlers=handlers,
            lease_ttl=lease_ttl,
            clock=self._clock,
        )

    async def start(self, packet_id: str) -> UUID:
        return await self._engine.start_first_product(packet_id)

    async def run_once(self) -> WorkerResult:
        return await self._worker.run_once()

    async def drain(self, *, max_jobs: int) -> tuple[WorkerResult, ...]:
        if max_jobs < 1:
            raise ValueError("max_jobs must be positive")
        results: list[WorkerResult] = []
        for _ in range(max_jobs + 1):
            result = await self.run_once()
            results.append(result)
            if result.status == "idle":
                return tuple(results)
            if result.status == "failed":
                return tuple(results)
        raise RuntimeError("worker did not become idle within max_jobs")


__all__ = ["FirstProductRuntime"]
