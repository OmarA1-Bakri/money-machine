"""Production handler registry for the first-product vertical slice."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.agents.implementations.creative_assets import CreativeAssetService
from money_machine.agents.implementations.preflight import PreflightService
from money_machine.application.services.listing_service import ListingService
from money_machine.application.services.product_service import ProductService
from money_machine.domain.enums import ProductState
from money_machine.domain.events import DomainEvent, DomainEventName
from money_machine.domain.models.candidate import CandidateShortlist
from money_machine.domain.models.job import JobEnvelope
from money_machine.domain.models.listing import ListingPackage, PreflightResult
from money_machine.domain.models.product import BuildResult, ProductQAResult
from money_machine.domain.models.product_spec import DedupeResult, ProductSpec
from money_machine.domain.models.research import ResearchPacket
from money_machine.domain.models.workflow import WorkflowBlocker, workflow_blocker_payload
from money_machine.domain.services.dedupe import DedupeService
from money_machine.domain.services.low_ticket import QualificationService
from money_machine.domain.services.product_rules import ProductRules, ProductStrategyService
from money_machine.domain.value_objects import FrozenModel, canonical_sha256
from money_machine.orchestration.worker import (
    HandlerOutcome,
    JobHandler,
    TerminalHandlerOutcome,
)
from money_machine.orchestration.workflows.product_experiment import (
    FIRST_PRODUCT_JOB_SEQUENCE,
    FIRST_PRODUCT_STEP_OUTPUTS,
)
from money_machine.persistence.database import Database
from money_machine.persistence.repositories.listings import ListingRepository
from money_machine.persistence.repositories.products import ProductRepository
from money_machine.persistence.repositories.research import ResearchRepository
from money_machine.persistence.repositories.workflows import WorkflowRepository
from money_machine.persistence.tables import domain_events, jobs, product_specs


class FirstProductResultStore:
    """Load exact durable workflow results without an in-memory shadow state machine."""

    def __init__(self, database: Database) -> None:
        self._database = database

    async def packet_for_workflow(self, workflow_run_id: UUID) -> ResearchPacket:
        async with self._database.session_factory() as session:
            workflow = await WorkflowRepository(session).get(workflow_run_id)
            if workflow is None:
                raise LookupError("workflow is absent")
            packet = await ResearchRepository(session).get_packet(workflow.packet_id)
            if packet is None:
                raise LookupError("admitted research packet is absent")
            return packet

    async def load_result[ResultT](
        self,
        workflow_run_id: UUID,
        job_type: str,
        result_model: type[ResultT],
    ) -> ResultT:
        contract = FIRST_PRODUCT_STEP_OUTPUTS.get(job_type)
        if contract is None or contract.result_model is not result_model:
            raise TypeError("requested result does not match the exact step contract")
        async with self._database.session_factory() as session:
            row = (
                await session.execute(
                    select(jobs.c.job_id, jobs.c.state).where(
                        jobs.c.workflow_run_id == workflow_run_id,
                        jobs.c.job_type == job_type,
                    )
                )
            ).one_or_none()
            if row is None or row.state != "SUCCEEDED":
                raise LookupError(f"{job_type} has no durable successful result")
            payloads = (
                (
                    await session.execute(
                        select(domain_events.c.payload).where(domain_events.c.job_id == row.job_id)
                    )
                )
                .scalars()
                .all()
            )
            if len(payloads) != 1:
                raise LookupError(f"{job_type} must have exactly one durable event")
            event = DomainEvent.model_validate_json(json.dumps(payloads[0]))
            if event.name is not contract.event_name:
                raise ValueError(f"{job_type} durable event does not match its contract")
            result = await self._load_identity(session, result_model, event.payload)
        if type(result) is not result_model:
            raise TypeError(f"{job_type} durable result model mismatch")
        return cast(ResultT, result)

    async def catalogue(self, *, exclude_product_spec_id: str) -> tuple[ProductSpec, ...]:
        async with self._database.session_factory() as session:
            payloads = (
                await session.execute(
                    select(product_specs.c.payload)
                    .where(product_specs.c.product_spec_id != exclude_product_spec_id)
                    .order_by(product_specs.c.product_spec_id)
                )
            ).scalars()
            return tuple(
                ProductSpec.model_validate_json(json.dumps(payload)) for payload in payloads
            )

    @staticmethod
    async def _load_identity(
        session: AsyncSession,
        result_model: type[object],
        payload: object,
    ) -> object:
        if not isinstance(payload, Mapping):
            raise ValueError("durable event payload is not a mapping")
        values = cast(Mapping[str, object], payload)
        research = ResearchRepository(session)
        products = ProductRepository(session)
        listings = ListingRepository(session)
        if result_model is ResearchPacket:
            return await research.get_packet(_identity(values, "packet_id"))
        if result_model is CandidateShortlist:
            return await research.get_shortlist(_identity(values, "shortlist_id"))
        if result_model is ProductSpec:
            return await products.get_spec(_identity(values, "product_spec_id"))
        if result_model is DedupeResult:
            return await products.get_dedupe(_identity(values, "dedupe_result_id"))
        if result_model is BuildResult:
            return await products.get_build(_identity(values, "build_id"))
        if result_model is ProductQAResult:
            return await products.get_qa(_identity(values, "qa_result_id"))
        if result_model is ListingPackage:
            return await listings.get_package(_identity(values, "listing_package_id"))
        if result_model is PreflightResult:
            return await listings.get_preflight(_identity(values, "preflight_result_id"))
        raise TypeError("unsupported first-product durable result model")


class FirstProductHandlers:
    """Compose approved lane services into exact Worker outcomes."""

    def __init__(
        self,
        database: Database,
        *,
        artifact_root: Path,
        product_rules: ProductRules,
        product_service: ProductService,
        clock: Callable[[], datetime],
    ) -> None:
        self._store = FirstProductResultStore(database)
        self._artifact_root = artifact_root
        self._rules = product_rules
        self._product = product_service
        self._clock = clock
        self._qualification = QualificationService()
        self._strategy = ProductStrategyService()
        self._dedupe = DedupeService()
        self._listing = ListingService()
        self._creative = CreativeAssetService()

    def registry(self) -> dict[str, JobHandler]:
        handlers: dict[str, JobHandler] = {
            "ADMIT_RESEARCH_PACKET": self.admit_research_packet,
            "QUALIFY_CANDIDATES": self.qualify_candidates,
            "CREATE_PRODUCT_SPEC": self.create_product_spec,
            "CHECK_CATALOGUE_DEDUPE": self.check_catalogue_dedupe,
            "BUILD_PRODUCT": self.build_product,
            "RUN_PRODUCT_QA": self.run_product_qa,
            "CREATE_LISTING_PACKAGE": self.create_listing_package,
            "RUN_PREFLIGHT": self.run_preflight,
        }
        if tuple(handlers) != FIRST_PRODUCT_JOB_SEQUENCE:
            raise RuntimeError("first-product handler registry does not match the frozen workflow")
        return handlers

    async def admit_research_packet(self, job: JobEnvelope) -> HandlerOutcome:
        packet = await self._store.packet_for_workflow(job.workflow_run_id)
        return self._success(job, packet)

    async def qualify_candidates(self, job: JobEnvelope) -> HandlerOutcome | TerminalHandlerOutcome:
        packet = await self._store.load_result(
            job.workflow_run_id, "ADMIT_RESEARCH_PACKET", ResearchPacket
        )
        scores = self._qualification.score(packet)
        shortlist = self._qualification.shortlist(packet, scores)
        if shortlist.selected_candidate_id is None:
            return self._terminal(
                job,
                shortlist,
                ProductState.INSUFFICIENT_EVIDENCE,
                "INSUFFICIENT_EVIDENCE",
                "research evidence did not produce a qualifying primary and backup",
            )
        return self._success(job, shortlist)

    async def create_product_spec(self, job: JobEnvelope) -> HandlerOutcome:
        shortlist = await self._store.load_result(
            job.workflow_run_id, "QUALIFY_CANDIDATES", CandidateShortlist
        )
        if shortlist.selected_candidate_id is None:
            raise ValueError("terminal shortlist cannot create a ProductSpec")
        selected = next(
            score
            for score in shortlist.candidates
            if score.candidate_id == shortlist.selected_candidate_id
        )
        packet = await self._store.packet_for_workflow(job.workflow_run_id)
        spec = self._strategy.create_spec(packet, shortlist, selected, self._rules)
        return self._success(job, spec)

    async def check_catalogue_dedupe(
        self, job: JobEnvelope
    ) -> HandlerOutcome | TerminalHandlerOutcome:
        spec = await self._store.load_result(
            job.workflow_run_id, "CREATE_PRODUCT_SPEC", ProductSpec
        )
        result = self._dedupe.evaluate(
            spec,
            await self._store.catalogue(exclude_product_spec_id=spec.product_spec_id),
        )
        if not result.passed:
            return self._terminal(
                job,
                result,
                ProductState.REJECTED,
                "CATALOGUE_DUPLICATE",
                "catalogue dedupe rejected the ProductSpec",
            )
        return self._success(job, result)

    async def build_product(self, job: JobEnvelope) -> HandlerOutcome:
        spec = await self._store.load_result(
            job.workflow_run_id, "CREATE_PRODUCT_SPEC", ProductSpec
        )
        dedupe = await self._store.load_result(
            job.workflow_run_id, "CHECK_CATALOGUE_DEDUPE", DedupeResult
        )
        return self._success(
            job,
            self._product.build_local_product(spec, dedupe, job.workflow_run_id),
        )

    async def run_product_qa(self, job: JobEnvelope) -> HandlerOutcome | TerminalHandlerOutcome:
        build = await self._store.load_result(job.workflow_run_id, "BUILD_PRODUCT", BuildResult)
        result = self._product.run_product_qa(build)
        if not result.passed:
            return self._terminal(
                job,
                result,
                ProductState.REJECTED,
                "PRODUCT_QA_FAILED",
                "product QA rejected the built product",
            )
        return self._success(job, result)

    async def create_listing_package(self, job: JobEnvelope) -> HandlerOutcome:
        spec = await self._store.load_result(
            job.workflow_run_id, "CREATE_PRODUCT_SPEC", ProductSpec
        )
        build = await self._store.load_result(job.workflow_run_id, "BUILD_PRODUCT", BuildResult)
        qa = await self._store.load_result(job.workflow_run_id, "RUN_PRODUCT_QA", ProductQAResult)
        package = self._listing.create(spec, build, qa)
        package = self._creative.render(
            package,
            self._artifact_root / str(job.workflow_run_id),
            spec=spec,
            build=build,
        )
        return self._success(job, package)

    async def run_preflight(self, job: JobEnvelope) -> HandlerOutcome | TerminalHandlerOutcome:
        spec = await self._store.load_result(
            job.workflow_run_id, "CREATE_PRODUCT_SPEC", ProductSpec
        )
        build = await self._store.load_result(job.workflow_run_id, "BUILD_PRODUCT", BuildResult)
        qa = await self._store.load_result(job.workflow_run_id, "RUN_PRODUCT_QA", ProductQAResult)
        package = await self._store.load_result(
            job.workflow_run_id, "CREATE_LISTING_PACKAGE", ListingPackage
        )
        preflight = PreflightService(self._artifact_root / str(job.workflow_run_id))
        try:
            result = preflight.evaluate(
                package,
                qa,
                spec=spec,
                build=build,
                now=self._clock(),
                external_effect_mode="simulation",
            )
        finally:
            preflight.close()
        if not result.passed:
            return self._terminal(
                job,
                result,
                ProductState.REJECTED,
                "PREFLIGHT_FAILED",
                "draft preflight rejected the local listing package",
            )
        return self._success(job, result)

    def _success(self, job: JobEnvelope, result: FrozenModel) -> HandlerOutcome:
        contract = FIRST_PRODUCT_STEP_OUTPUTS[job.job_type]
        identity = _result_identity(result)
        payload = {_identity_field(result): identity}
        return HandlerOutcome(
            result_type=contract.result_type,
            result=result,
            event=DomainEvent(
                event_id=job.job_id,
                workflow_run_id=job.workflow_run_id,
                job_id=job.job_id,
                name=contract.event_name,
                occurred_at=self._clock(),
                payload=payload,
                payload_sha256=canonical_sha256(payload),
            ),
            successor_job_type=contract.successor_job_type,
        )

    def _terminal(
        self,
        job: JobEnvelope,
        result: FrozenModel,
        state: ProductState,
        code: str,
        message: str,
    ) -> TerminalHandlerOutcome:
        contract = FIRST_PRODUCT_STEP_OUTPUTS[job.job_type]
        occurred_at = self._clock()
        blocker = WorkflowBlocker(
            blocker_id=f"blocker:{job.job_id}:{state.value}",
            job_id=job.job_id,
            terminal_state=state,
            code=code,
            message=message,
            result_type=contract.result_type,
            result_id=_result_identity(result),
            result_sha256=canonical_sha256(result),
            occurred_at=occurred_at,
        )
        payload = workflow_blocker_payload(blocker)
        event_name = {
            ProductState.INSUFFICIENT_EVIDENCE: DomainEventName.INSUFFICIENT_EVIDENCE,
            ProductState.REJECTED: DomainEventName.WORKFLOW_REJECTED,
            ProductState.FAILED: DomainEventName.WORKFLOW_FAILED,
        }[state]
        return TerminalHandlerOutcome(
            result_type=contract.result_type,
            result=result,
            blocker=blocker,
            event=DomainEvent(
                event_id=job.job_id,
                workflow_run_id=job.workflow_run_id,
                job_id=job.job_id,
                name=event_name,
                occurred_at=occurred_at,
                payload=payload,
                payload_sha256=canonical_sha256(payload),
            ),
        )


def _identity(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"durable event is missing {field}")
    return value


def _identity_field(result: FrozenModel) -> str:
    if type(result) is ResearchPacket:
        return "packet_id"
    if type(result) is CandidateShortlist:
        return "shortlist_id"
    if type(result) is ProductSpec:
        return "product_spec_id"
    if type(result) is DedupeResult:
        return "dedupe_result_id"
    if type(result) is BuildResult:
        return "build_id"
    if type(result) is ProductQAResult:
        return "qa_result_id"
    if type(result) is ListingPackage:
        return "listing_package_id"
    if type(result) is PreflightResult:
        return "preflight_result_id"
    raise TypeError("unsupported first-product result model")


def _result_identity(result: FrozenModel) -> str:
    value = getattr(result, _identity_field(result))
    if not isinstance(value, str) or not value:
        raise ValueError("first-product result identity is invalid")
    return value


__all__ = ["FirstProductHandlers", "FirstProductResultStore"]
