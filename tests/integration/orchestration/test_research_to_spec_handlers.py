from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import cast
from uuid import UUID

from alembic import command
from alembic.config import Config
from sqlalchemy import func, insert, select

from money_machine.agents.implementations.catalogue_dedupe import CatalogueDedupeHandler
from money_machine.agents.implementations.market_research import MarketResearchHandler
from money_machine.agents.implementations.product_strategy import ProductStrategyHandler
from money_machine.application.services.research_service import ResearchService
from money_machine.domain.enums import JobState, ProductState, RetryClass
from money_machine.domain.events import DomainEvent, DomainEventName
from money_machine.domain.models.candidate import CandidateShortlist, QualificationScore
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.domain.models.research import ResearchPacket
from money_machine.domain.models.workflow import WorkflowRun
from money_machine.domain.services.product_rules import ProductRules
from money_machine.domain.value_objects import canonical_sha256
from money_machine.persistence.database import Database
from money_machine.persistence.tables import (
    candidate_shortlists,
    domain_events,
    job_dependencies,
    product_specs,
    qualification_scores,
)
from money_machine.persistence.unit_of_work import UnitOfWork

NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_WORKFLOW_ID = UUID(int=99)


def _job(number: int, job_type: str, *, workflow_id: UUID = FIXTURE_WORKFLOW_ID) -> JobEnvelope:
    return JobEnvelope(
        job_id=UUID(int=number),
        workflow_run_id=workflow_id,
        job_type=job_type,
        # Handlers receive the typed envelope directly in these composition tests;
        # durable RUNNING state is only valid after a lease-bound worker claim.
        state=JobState.READY,
        idempotency_key=f"fixture-{workflow_id}-{number}",
        input_sha256=f"{number:064x}",
        retry_class=RetryClass.NEVER,
        max_attempts=1,
    )


def _packet(*, low_supply: bool = False) -> ResearchPacket:
    packet = ResearchService().import_packet(
        Path("tests/fixtures/research/valid_packet_30.json"), now=NOW
    )
    if not low_supply:
        return packet
    return packet.model_copy(
        update={
            "observations": tuple(
                observation.model_copy(
                    update={
                        "qualification_inputs": {
                            dimension: Decimal("0")
                            for dimension in observation.qualification_inputs
                        }
                    }
                )
                for observation in packet.observations
            )
        }
    )


class FakeResearchRepository:
    def __init__(self, *, low_supply: bool = False) -> None:
        self.packet = _packet(low_supply=low_supply)
        self.results: dict[UUID, object] = {UUID(int=1): self.packet}
        self.loads: list[tuple[UUID, type[object]]] = []
        self.persisted: tuple[tuple[QualificationScore, ...], CandidateShortlist | None] | None = (
            None
        )
        self.catalogue: tuple[ProductSpec, ...] = ()

    async def load_predecessor_result[Result](
        self, job_id: UUID, result_type: type[Result]
    ) -> Result:
        self.loads.append((job_id, cast(type[object], result_type)))
        value = self.results[job_id]
        if not isinstance(value, result_type):
            raise TypeError("unexpected predecessor result")
        return value

    async def persist_qualification(
        self,
        packet_id: str,
        scores: tuple[QualificationScore, ...],
        shortlist: CandidateShortlist | None,
    ) -> None:
        assert packet_id == self.packet.packet_id
        self.persisted = (scores, shortlist)

    async def load_packet(self, packet_id: str) -> ResearchPacket:
        assert packet_id == self.packet.packet_id
        return self.packet

    async def load_catalogue(self) -> tuple[ProductSpec, ...]:
        return self.catalogue


def test_handlers_load_exact_predecessors_and_emit_declared_typed_results() -> None:
    async def scenario() -> None:
        repository = FakeResearchRepository()
        shortlist_outcome = await MarketResearchHandler(repository).handle(
            _job(1, "SCORE_AND_SHORTLIST")
        )
        assert shortlist_outcome.event_name is DomainEventName.CANDIDATE_SHORTLISTED
        assert shortlist_outcome.terminal_state is None
        assert shortlist_outcome.next_job_type == "CREATE_PRODUCT_SPEC"
        assert shortlist_outcome.result is not None
        assert repository.persisted == (shortlist_outcome.scores, shortlist_outcome.result)
        repository.results[UUID(int=2)] = shortlist_outcome.result

        spec_outcome = await ProductStrategyHandler(repository, ProductRules.default()).handle(
            _job(2, "CREATE_PRODUCT_SPEC")
        )
        assert spec_outcome.event_name is DomainEventName.PRODUCT_SPEC_CREATED
        repository.results[UUID(int=3)] = spec_outcome.result

        dedupe_outcome = await CatalogueDedupeHandler(repository).handle(_job(3, "RUN_DEDUPE"))
        assert dedupe_outcome.event_name is DomainEventName.DEDUPE_PASSED
        assert dedupe_outcome.result.passed
        assert repository.loads == [
            (UUID(int=1), type(repository.packet)),
            (UUID(int=2), type(shortlist_outcome.result)),
            (UUID(int=3), type(spec_outcome.result)),
        ]

    asyncio.run(scenario())


def test_low_supply_is_terminal_and_never_declares_product_successor() -> None:
    async def scenario() -> None:
        repository = FakeResearchRepository(low_supply=True)
        outcome = await MarketResearchHandler(repository).handle(_job(1, "SCORE_AND_SHORTLIST"))
        assert outcome.result is None
        assert outcome.event_name is None
        assert outcome.terminal_state is ProductState.INSUFFICIENT_EVIDENCE
        assert outcome.next_job_type is None
        assert repository.persisted == (outcome.scores, None)

    asyncio.run(scenario())


def test_handlers_reject_wrong_job_types_before_repository_access() -> None:
    async def scenario() -> None:
        repository = FakeResearchRepository()
        for handler in (
            MarketResearchHandler(repository),
            ProductStrategyHandler(repository, ProductRules.default()),
            CatalogueDedupeHandler(repository),
        ):
            repository.loads.clear()
            try:
                await handler.handle(_job(1, "BUILD_LOCAL_PRODUCT"))
            except ValueError as exc:
                assert "job type" in str(exc)
            else:
                raise AssertionError("handler accepted an undeclared job type")
            assert repository.loads == []

    asyncio.run(scenario())


class PostgreSQLHandlerRepository:
    """Test adapter proving Task 5 contracts compose with Task 3 PostgreSQL state."""

    def __init__(self, database: Database) -> None:
        self._database = database
        self._loaded_product_spec_id: str | None = None

    async def _predecessor_payload(self, job_id: UUID) -> dict[str, object]:
        async with self._database.session_factory() as session:
            predecessor_id = await session.scalar(
                select(job_dependencies.c.depends_on_job_id).where(
                    job_dependencies.c.job_id == job_id
                )
            )
            if predecessor_id is None:
                raise LookupError("job has no exact predecessor")
            payload = await session.scalar(
                select(domain_events.c.payload)
                .where(domain_events.c.job_id == predecessor_id)
                .order_by(domain_events.c.occurred_at.desc(), domain_events.c.event_id.desc())
                .limit(1)
            )
            if not isinstance(payload, dict):
                raise LookupError("predecessor has no durable result event")
            event_record = cast(dict[str, object], payload)
            event_payload = event_record.get("payload")
            if not isinstance(event_payload, dict):
                raise LookupError("predecessor event has no typed result payload")
            return cast(dict[str, object], event_payload)

    async def load_predecessor_result[Result](
        self, job_id: UUID, result_type: type[Result]
    ) -> Result:
        payload = await self._predecessor_payload(job_id)
        result: object | None
        async with UnitOfWork(self._database) as uow:
            if result_type is ResearchPacket:
                result = await uow.research.get_packet(cast(str, payload["packet_id"]))
            elif result_type is CandidateShortlist:
                result = await uow.research.get_shortlist(cast(str, payload["shortlist_id"]))
            elif result_type is ProductSpec:
                product_spec_id = cast(str, payload["product_spec_id"])
                self._loaded_product_spec_id = product_spec_id
                result = await uow.products.get_spec(product_spec_id)
            else:
                raise TypeError("unsupported predecessor result type")
        if result is None:
            raise LookupError("exact predecessor result is absent")
        return cast(Result, result)

    async def persist_qualification(
        self,
        packet_id: str,
        scores: tuple[QualificationScore, ...],
        shortlist: CandidateShortlist | None,
    ) -> None:
        async with UnitOfWork(self._database) as uow:
            for score in scores:
                await uow.research.add_score(packet_id, score)
            if shortlist is not None:
                await uow.research.add_shortlist(shortlist)

    async def load_packet(self, packet_id: str) -> ResearchPacket:
        async with UnitOfWork(self._database) as uow:
            packet = await uow.research.get_packet(packet_id)
        if packet is None:
            raise LookupError("packet is absent")
        return packet

    async def load_catalogue(self) -> tuple[ProductSpec, ...]:
        async with self._database.session_factory() as session:
            rows = await session.scalars(
                select(product_specs.c.payload)
                .where(product_specs.c.product_spec_id != self._loaded_product_spec_id)
                .order_by(product_specs.c.product_spec_id)
            )
            return tuple(ProductSpec.model_validate_json(json.dumps(row)) for row in rows)


def _event(
    number: int,
    workflow_id: UUID,
    job_id: UUID,
    name: DomainEventName,
    payload: dict[str, object],
) -> DomainEvent:
    return DomainEvent(
        event_id=UUID(int=number),
        workflow_run_id=workflow_id,
        job_id=job_id,
        name=name,
        occurred_at=NOW,
        payload=payload,
        payload_sha256=canonical_sha256(payload),
    )


def test_postgresql_handlers_persist_all_scores_and_load_exact_predecessors() -> None:
    config = Config(str(REPO_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
    command.upgrade(config, "head")

    async def scenario() -> None:
        database = Database.from_url(os.environ["MONEY_MACHINE_TEST_DATABASE_URL"])
        workflow_id = UUID(int=700)
        packet = _packet()
        jobs = (
            _job(701, "ADMIT_RESEARCH_PACKET", workflow_id=workflow_id),
            _job(702, "SCORE_AND_SHORTLIST", workflow_id=workflow_id),
            _job(703, "CREATE_PRODUCT_SPEC", workflow_id=workflow_id),
            _job(704, "RUN_DEDUPE", workflow_id=workflow_id),
        )
        workflow = WorkflowRun(
            workflow_run_id=workflow_id,
            workflow_type="FIRST_PRODUCT",
            packet_id=packet.packet_id,
            state=ProductState.RESEARCHED,
            idempotency_key=f"workflow:{packet.packet_id}",
            created_at=NOW,
            updated_at=NOW,
        )
        async with UnitOfWork(database) as uow:
            await uow.workflows.add(workflow)
            await uow.research.add_packet(packet)
            for job in jobs:
                await uow.jobs.add(job)
            assert uow.session is not None
            await uow.session.execute(
                insert(job_dependencies),
                [
                    {"job_id": jobs[1].job_id, "depends_on_job_id": jobs[0].job_id},
                    {"job_id": jobs[2].job_id, "depends_on_job_id": jobs[1].job_id},
                    {"job_id": jobs[3].job_id, "depends_on_job_id": jobs[2].job_id},
                ],
            )
            await uow.events.add(
                _event(
                    710,
                    workflow_id,
                    jobs[0].job_id,
                    DomainEventName.RESEARCH_PACKET_ADMITTED,
                    {"packet_id": packet.packet_id},
                )
            )

        repository = PostgreSQLHandlerRepository(database)
        shortlist_outcome = await MarketResearchHandler(repository).handle(jobs[1])
        assert shortlist_outcome.result is not None
        async with database.session_factory() as session:
            assert await session.scalar(
                select(func.count()).select_from(qualification_scores)
            ) == len(shortlist_outcome.scores)
            assert await session.scalar(select(func.count()).select_from(candidate_shortlists)) == 1

        async with UnitOfWork(database) as uow:
            await uow.events.add(
                _event(
                    711,
                    workflow_id,
                    jobs[1].job_id,
                    DomainEventName.CANDIDATE_SHORTLISTED,
                    {"shortlist_id": shortlist_outcome.result.shortlist_id},
                )
            )
        spec_outcome = await ProductStrategyHandler(repository, ProductRules.default()).handle(
            jobs[2]
        )
        async with UnitOfWork(database) as uow:
            await uow.products.add_spec(spec_outcome.result)
            await uow.events.add(
                _event(
                    712,
                    workflow_id,
                    jobs[2].job_id,
                    DomainEventName.PRODUCT_SPEC_CREATED,
                    {"product_spec_id": spec_outcome.result.product_spec_id},
                )
            )
        dedupe_outcome = await CatalogueDedupeHandler(repository).handle(jobs[3])
        assert dedupe_outcome.result.passed
        await database.dispose()

    asyncio.run(scenario())
