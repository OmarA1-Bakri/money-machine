"""Finite fixture consumers of the existing build/repair/retest workflow.

No live adapter, LLM call, commissioning bypass, scheduler or second job store.
The caller gives this application boundary a dedicated unit of work: it commits
repair intent before changing the durable fixture, and terminal evidence after.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from sqlalchemy import select

from money_machine.agents.implementations.notion_product_builder import (
    ProductBuildCheckpoint,
    ProductBuildError,
    require_probe,
    require_same_spec,
)
from money_machine.agents.implementations.notion_progress import (
    load_payload,
    record_applied_repairs,
)
from money_machine.agents.implementations.notion_progress_record import write_checkpoint
from money_machine.agents.implementations.notion_qa import (
    PHASE_FACT_LEDGER,
    formula_repair_targets,
    live_qa_passed,
    load_qa_record,
    run_product_qa,
)
from money_machine.agents.implementations.notion_variants import (
    build_variants,
    load_variant_checkpoint,
)
from money_machine.agents.registry import AgentRegistry
from money_machine.config.settings import TelemetryConfig
from money_machine.domain.enums import AgentRunStatus, JobStatus, RetryClass, SideEffectClass
from money_machine.domain.events import EventName
from money_machine.domain.models.common import ContractError
from money_machine.domain.models.product_spec import ProductSpec
from money_machine.integrations.notion.domain import NotionFormula
from money_machine.integrations.notion.fixture_adapter import FixtureNotionAdapter
from money_machine.integrations.posthog.client import PostHogClient
from money_machine.observability.agent_runs import AgentRunObserver
from money_machine.observability.correlation import CorrelationContext
from money_machine.observability.logging import StructuredLogSink
from money_machine.orchestration.event_dispatcher import EventDispatcher
from money_machine.orchestration.idempotency import (
    mark_idempotency_completed,
    record_effect_attempt,
    reserve_idempotency_key,
)
from money_machine.orchestration.leases import release_lease
from money_machine.orchestration.retry import evaluate_retry
from money_machine.orchestration.transition_guard import require_job_transition
from money_machine.persistence import tables as t
from money_machine.persistence.unit_of_work import UnitOfWork

ROOT = Path(__file__).resolve().parents[3]
OPERATION = "notion.fixture.update_formula"


def _checkpoint(path: Path) -> ProductBuildCheckpoint:
    stored, _ = load_variant_checkpoint(path)
    return replace(stored, qa=load_qa_record(path), next_phase=PHASE_FACT_LEDGER)


async def run_fixture_qa_jobs(
    uow: UnitOfWork,
    build_job: t.Job,
    spec: ProductSpec,
    probe: FixtureNotionAdapter,
    path: Path,
    *,
    recorded_at: datetime,
) -> ProductBuildCheckpoint:
    """Execute one bounded formula repair and automatic retest, in simulation only."""
    require_probe(probe)
    require_same_spec(_checkpoint(path), spec)
    if (
        build_job.allowed_mode != "simulation"
        or build_job.job_type != "ProductBuildJob"
        or build_job.workflow_id != spec.workflow_id
        or build_job.object_id != spec.product_id
    ):
        raise ProductBuildError("fixture QA requires its simulation build job")
    observer = AgentRunObserver(
        uow=uow,
        telemetry=PostHogClient(TelemetryConfig(version=1, enabled=False, allowed_events=())),
        log_sink=StructuredLogSink(stream=sys.stderr),
    )

    async def successor(parent: t.Job, event: EventName, kind: str) -> t.Job:
        await EventDispatcher(uow).dispatch(
            event_name=event,
            aggregate_type="products",
            aggregate_id=spec.product_id,
            workflow_id=spec.workflow_id,
            job_id=parent.id,
            occurred_at=recorded_at,
        )
        child = (
            await uow.session.scalars(
                select(t.Job).where(
                    t.Job.workflow_id == spec.workflow_id,
                    t.Job.job_type == kind,
                    t.Job.input["parent_job_id"].astext == str(parent.id),
                )
            )
        ).one()
        child.object_type, child.object_id = "products", spec.product_id
        return child

    async def qa() -> str:
        result = await run_product_qa(spec, probe, path, recorded_at=recorded_at)
        assert result.qa is not None
        return result.qa.verdict

    async def execute(job: t.Job, action: Callable[[], Awaitable[str]]) -> str:
        # Existing job row is the lock and identity; no parallel execution store.
        await uow.session.refresh(job, with_for_update=True)
        if job.allowed_mode != "simulation":
            raise ProductBuildError("fixture QA refuses provider mode")
        if job.status == "SUCCEEDED":
            run = (
                await uow.session.scalars(
                    select(t.AgentRun)
                    .where(t.AgentRun.job_id == job.id, t.AgentRun.status == "SUCCESS")
                    .order_by(t.AgentRun.run_number.desc())
                    .limit(1)
                )
            ).one()
            verdict = str(run.output["verdict"])
            if (
                job.job_type == "ProductQAJob"
                and verdict == "PASS"
                and not await live_qa_passed(probe, _checkpoint(path), spec)
            ):
                raise ProductBuildError("completed fixture QA no longer holds")
            _link_execution(path, job, run)
            return verdict
        now = datetime.now(UTC)
        if job.status == "RUNNING":
            raise ProductBuildError("fixture QA job requires existing lease recovery")
        if job.attempt >= job.max_attempts or job.status == "TERMINAL_FAILURE":
            if job.status == "FAILED":
                require_job_transition(JobStatus.FAILED, JobStatus.TERMINAL_FAILURE)
                job.status = "TERMINAL_FAILURE"
                await uow.commit()
            raise ProductBuildError("fixture QA retry budget exhausted")
        if job.status == "FAILED":
            targets = job.input.get("formula_targets", [])
            resolved = bool(targets) and all(
                _target_expression(probe, row[0], row[1]) in (row[2], row[3]) for row in targets
            )
            decision = evaluate_retry(
                retry_class=RetryClass(job.retry_class),
                current_attempt=max(0, job.attempt - 1),
                max_attempts=job.max_attempts,
                reconciliation_resolved=resolved,
                # Finite local simulation uses the policy's budget/eligibility,
                # with no provider rate-limit delay or blocking sleeps.
                base_delay_seconds=0,
                now=now,
            )
            if not decision.can_retry:
                raise ProductBuildError("fixture QA retry requires reconciliation")
        status = JobStatus(job.status)
        if status != JobStatus.READY:
            require_job_transition(status, JobStatus.READY)
            job.status = "READY"
        require_job_transition(JobStatus.READY, JobStatus.RUNNING)
        job.attempt += 1
        definition = (
            await uow.session.scalars(
                select(t.AgentDefinition).where(t.AgentDefinition.agent_id == job.owner_agent_id)
            )
        ).one()
        runtime = AgentRegistry.from_yaml(ROOT).get(job.owner_agent_id)
        prompt = (
            await uow.session.scalars(
                select(t.PromptVersion).where(
                    t.PromptVersion.prompt_reference == runtime.system_prompt_reference
                )
            )
        ).one_or_none()
        if prompt is None:
            # Same real fixture-library prompt registration used by FixtureRun.
            sources = tuple(
                (ROOT / "src/money_machine/agents/prompts").glob(job.owner_agent_id + "_*.md")
            )
            if len(sources) != 1:
                raise ProductBuildError("fixture QA prompt source is ambiguous")
            source = sources[0]
            prompt = t.PromptVersion(
                prompt_reference=runtime.system_prompt_reference,
                version=1,
                sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                source_path=str(source.relative_to(ROOT)),
            )
            uow.session.add(prompt)
            await uow.flush()
        if hashlib.sha256((ROOT / prompt.source_path).read_bytes()).hexdigest() != prompt.sha256:
            raise ProductBuildError("fixture QA prompt source changed")
        context = observer.begin_run(
            correlation=CorrelationContext(
                job.id,
                job.owner_agent_id,
                job.workflow_id,
                job_type=job.job_type,
                attempt=job.attempt,
            ),
            agent_definition_id=definition.id,
            agent_definition_version=definition.contract_version,
            prompt_version_id=prompt.id,
            prompt_reference=prompt.prompt_reference,
            prompt_sha256=prompt.sha256,
            run_number=await observer.next_run_number(job.id),
            model=None,
            input_payload={"spec_id": str(spec.spec_id), "mode": "fixture"},
        )
        job.status, job.lease_owner = "RUNNING", str(context.run_id)
        job.lease_expires_at = now + timedelta(minutes=5)
        try:
            verdict = await action()
        except Exception:
            run = await observer.finalize_run(
                context,
                status=AgentRunStatus.FAILURE,
                output={"execution_kind": "deterministic_fixture_library", "prompt_used": False},
                error=ContractError(
                    code="FIXTURE_QA_INTERRUPTED",
                    message="fixture repair interrupted",
                    retryable=True,
                ),
                token_count=0,
            )
            await release_lease(
                uow.session,
                job_id=job.id,
                worker_id=str(context.run_id),
                now=datetime.now(UTC),
                final_status=JobStatus.FAILED,
            )
            await uow.commit()
            _link_execution(path, job, run)
            raise ProductBuildError("fixture repair interrupted") from None
        blocked = verdict == "BLOCKED"
        run = await observer.finalize_run(
            context,
            status=AgentRunStatus.BLOCKED if blocked else AgentRunStatus.SUCCESS,
            output={
                "verdict": verdict,
                "execution_kind": "deterministic_fixture_library",
                "prompt_used": False,
            },
            token_count=0,
            error=ContractError(
                code="PRODUCT_QA_BLOCKED", message="fixture product QA blocked", retryable=True
            )
            if blocked
            else None,
        )
        await release_lease(
            uow.session,
            job_id=job.id,
            worker_id=str(context.run_id),
            now=datetime.now(UTC),
            final_status=JobStatus.BLOCKED if blocked else JobStatus.SUCCEEDED,
        )
        # A checkpoint may only cite a run once its owning records are durable.
        await uow.commit()
        _link_execution(path, job, run)
        return verdict

    first = await successor(build_job, EventName.BUILD_COMPLETED, "ProductQAJob")
    verdict = await execute(first, qa)
    if verdict == "BLOCKED":
        await uow.commit()
        return _checkpoint(path)
    verifying_job = first
    if verdict == "FAIL_REPAIRABLE":
        repair = await successor(first, EventName.BUILD_QA_FAILED, "BuildRepairJob")

        async def apply() -> str:
            await _repair_formulas(uow, repair, spec, probe, path, recorded_at)
            return "REPAIR_APPLIED"

        await execute(repair, apply)
        verifying_job = await successor(repair, EventName.REPAIR_APPLIED, "ProductQAJob")
        verdict = await execute(verifying_job, qa)
        if verdict == "PASS":
            # Verification closes the repair; the repair action cannot do this.
            key = f"fixture-qa:REPAIR_COMPLETED:{repair.id}"
            if await uow.events.by_dedupe_key(key) is None:
                await uow.events.append(
                    event_name=EventName.REPAIR_COMPLETED,
                    aggregate_type="products",
                    aggregate_id=spec.product_id,
                    dedupe_key=key,
                    workflow_id=spec.workflow_id,
                    job_id=verifying_job.id,
                    payload={"repair_job_id": str(repair.id)},
                    occurred_at=recorded_at,
                )
    if verdict == "PASS":
        variant_job = await successor(verifying_job, EventName.BUILD_QA_PASSED, "VariantBuildJob")

        async def verify_variants() -> str:
            # The fixture built variants before QA. Reconcile that real stage
            # through the existing idempotent builder, leaving no pending build.
            await build_variants(spec, probe, path, recorded_at=recorded_at)
            return "VARIANTS_VERIFIED"

        await execute(variant_job, verify_variants)
    await uow.commit()
    return _checkpoint(path)


async def _repair_formulas(uow, job, spec, probe, path, when) -> None:
    stored = _checkpoint(path)
    if "formula_targets" not in job.input:
        targets = formula_repair_targets(probe, stored, spec)
        if stored.qa is None or stored.qa.verdict != "FAIL_REPAIRABLE" or not targets:
            raise ProductBuildError("fixture formula repair has no verified targets")
        job.input = {**job.input, "formula_targets": [list(row) for row in targets]}
    key = f"{job.id}:notification_formulas"
    reservation = await uow.idempotency.by_key(key)
    if reservation is None:
        await reserve_idempotency_key(
            uow.session,
            idempotency_key=key,
            job_id=job.id,
            operation=OPERATION,
            side_effect_class=SideEffectClass.NONE,
            now=when,
        )
        # Durable intent before the local provider mutation. The lease prevents
        # another consumer from entering while this commit releases the row lock.
        await uow.commit()
    await uow.flush()
    await uow.session.refresh(job, with_for_update=True)
    receipt = (
        await uow.session.scalars(
            select(t.Receipt).where(
                t.Receipt.idempotency_key == key, t.Receipt.operation == OPERATION
            )
        )
    ).one_or_none()
    if reservation is not None and reservation.completed_at is not None and receipt is None:
        raise ProductBuildError("fixture repair completion is inconsistent")
    for database_id, property_id, previous, expected in job.input["formula_targets"]:
        database = probe.databases.get(database_id)
        matches = (
            [] if database is None else [p for p in database.properties if p.id == property_id]
        )
        if len(matches) != 1:
            raise ProductBuildError("fixture repair target changed")
        formula = matches[0].config.get("formula")
        if type(formula) is not NotionFormula or formula.expression not in (previous, expected):
            raise ProductBuildError("fixture repair target changed")
        if receipt is not None and formula.expression != expected:
            raise ProductBuildError("confirmed fixture repair no longer matches")
        if formula.expression != expected:
            await probe.update_formula(database_id, property_id, expected)
        # Fresh readback also reconciles accepted-write/lost-response retries.
        if matches[0].config["formula"].expression != expected:
            raise ProductBuildError("fixture repair readback failed")
    if receipt is None:
        await record_effect_attempt(
            uow.session,
            idempotency_key=key,
            job_id=job.id,
            agent_run_id=None,
            provider="notion_fixture",
            operation=OPERATION,
            effect_state="CONFIRMED",
            provider_object_id=stored.page_id,
            reconciliation_attempt=0,
            now=when,
        )
        uow.receipts.add(
            t.Receipt(
                job_id=job.id,
                idempotency_key=key,
                provider="notion_fixture",
                operation=OPERATION,
                side_effect_class="NONE",
                autonomy_mode="simulation",
                effect_state="CONFIRMED",
                provider_object_id=stored.page_id,
                safe_detail={"readback": "matched"},
                recorded_at=when,
            )
        )
        await mark_idempotency_completed(uow.session, idempotency_key=key, now=when)
    record_applied_repairs(path, ("notification_formulas",))


def _target_expression(probe, database_id, property_id) -> str | None:
    database = probe.databases.get(database_id)
    if database is None:
        return None
    matches = [prop for prop in database.properties if prop.id == property_id]
    if len(matches) != 1:
        return None
    formula = matches[0].config.get("formula")
    return formula.expression if type(formula) is NotionFormula else None


def _link_execution(path: Path, job: t.Job, run: t.AgentRun) -> None:
    envelope = load_payload(path)
    assert envelope.payload is not None
    payload = dict(cast(dict[str, Any], envelope.payload))
    references: dict[str, Any] = dict(payload["provider_object_references"])
    traces = list(references.get("qa_executions", []))
    trace = dict(
        job_id=str(job.id),
        parent_job_id=job.input.get("parent_job_id"),
        job_type=job.job_type,
        workflow_id=str(job.workflow_id),
        agent_run_id=str(run.id),
        agent_id=run.agent_id,
        agent_definition_id=str(run.agent_definition_id),
        agent_definition_version=run.agent_definition_version,
        prompt_version_id=str(run.prompt_version_id),
        prompt_reference=run.prompt_reference,
        prompt_sha256=run.prompt_sha256,
        identity_registry="money_machine.agent_definitions",
        thredos_registration="unverified",
    )
    if trace in traces:
        return
    references["qa_executions"] = [*traces, trace]
    payload["provider_object_references"] = references
    progress = json.loads(path.read_text(encoding="ascii"))["progress"]
    progress.pop("record_digest")
    write_checkpoint(path, preserved_payload=payload, progress=progress)
