"""Agent-run observability: persistence, structured logs, and PostHog-shaped events."""

from __future__ import annotations

import hashlib
import json
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from money_machine.domain.enums import AgentRunStatus
from money_machine.domain.models.common import ContractError
from money_machine.integrations.posthog.client import PostHogClient
from money_machine.observability.correlation import CorrelationContext
from money_machine.observability.logging import StructuredLogSink, emit_structured_log
from money_machine.observability.telemetry import emit_agent_run_completed, emit_agent_run_started
from money_machine.persistence.tables import AgentRun, AgentToolCall, Job
from money_machine.persistence.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class ToolCallObservation:
    """One tool invocation to persist against an agent run."""

    tool_id: str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any]
    duration_ms: int

    @property
    def input_hash(self) -> str:
        return _hash_payload(self.input_payload)

    @property
    def output_hash(self) -> str:
        return _hash_payload(self.output_payload)


@dataclass
class AgentRunObservationContext:
    """Identity of one execution, including its durable active checkpoint."""

    run_id: UUID
    correlation: CorrelationContext
    agent_definition_id: UUID
    agent_definition_version: int
    prompt_version_id: UUID
    prompt_reference: str
    prompt_sha256: str
    run_number: int
    model: str | None
    input_hash: str
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    job_attempt: int | None = None
    lease_owner: str | None = None


@dataclass
class AgentRunObserver:
    """Record agent runs, tool calls, structured logs, and telemetry events."""

    uow: UnitOfWork
    telemetry: PostHogClient
    log_sink: StructuredLogSink

    async def next_run_number(self, job_id: UUID) -> int:
        """Return the next run number for one job."""
        existing = await self.uow.agent_runs.for_job(job_id)
        if not existing:
            return 1
        return max(run.run_number for run in existing) + 1

    def begin_run(
        self,
        *,
        correlation: CorrelationContext,
        agent_definition_id: UUID,
        agent_definition_version: int,
        prompt_version_id: UUID,
        prompt_reference: str,
        prompt_sha256: str,
        run_number: int,
        model: str | None,
        input_payload: dict[str, Any],
    ) -> AgentRunObservationContext:
        """Start observability for one agent execution (log + telemetry only)."""
        run_id = uuid4()
        context = AgentRunObservationContext(
            run_id=run_id,
            correlation=CorrelationContext(
                job_id=correlation.job_id,
                agent_id=correlation.agent_id,
                workflow_id=correlation.workflow_id,
                agent_run_id=run_id,
                job_type=correlation.job_type,
                attempt=correlation.attempt,
            ),
            agent_definition_id=agent_definition_id,
            agent_definition_version=agent_definition_version,
            prompt_version_id=prompt_version_id,
            prompt_reference=prompt_reference,
            prompt_sha256=prompt_sha256,
            run_number=run_number,
            model=model,
            input_hash=_hash_payload(input_payload),
        )
        emit_structured_log(
            sink=self.log_sink,
            level="INFO",
            event_type="agent_run_started",
            message="agent run started",
            correlation=context.correlation,
            metadata={
                "prompt_reference": prompt_reference,
                "run_number": run_number,
                "model": model,
            },
        )
        with suppress(Exception):
            # Telemetry is best-effort and must never block execution.
            emit_agent_run_started(
                self.telemetry,
                correlation=context.correlation,
                agent_run_id=run_id,
                prompt_reference=prompt_reference,
                run_number=run_number,
                model=model,
            )
        return context

    async def persist_started_run(
        self, context: AgentRunObservationContext, *, lease_owner: str
    ) -> AgentRun:
        """Stage a real active run; the owning UoW MUST commit before execution.

        Lock the existing job to serialize starts. An interrupted active run is
        never automatically replaced, resumed or declared failed by this method.
        """
        session = self.uow.session
        await self.uow.flush()
        job = await session.scalar(
            select(Job)
            .where(Job.id == context.correlation.job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            job is None
            or job.owner_agent_id != context.correlation.agent_id
            or job.workflow_id != context.correlation.workflow_id
            or job.attempt != context.correlation.attempt
            or job.status != "RUNNING"
            or not lease_owner
            or job.lease_owner != lease_owner
            or job.lease_expires_at is None
            or job.lease_expires_at <= datetime.now(UTC)
        ):
            raise ValueError("active run requires matching running job and lease")
        existing = await self.uow.agent_runs.for_job(job.id)
        if any(run.status == "RUNNING" for run in existing):
            raise ValueError("job already has an unresolved active run")
        if context.run_number != max((run.run_number for run in existing), default=0) + 1:
            raise ValueError("active run number is stale")
        run = AgentRun(
            id=context.run_id,
            job_id=job.id,
            agent_definition_id=context.agent_definition_id,
            agent_id=context.correlation.agent_id,
            agent_definition_version=context.agent_definition_version,
            prompt_version_id=context.prompt_version_id,
            prompt_reference=context.prompt_reference,
            prompt_sha256=context.prompt_sha256,
            run_number=context.run_number,
            job_attempt=job.attempt,
            lease_owner=lease_owner,
            model=context.model,
            input_hash=context.input_hash,
            status="RUNNING",
            output={},
            error=None,
            started_at=context.started_at,
            completed_at=None,
        )
        self.uow.agent_runs.add(run)
        await self.uow.flush()
        context.job_attempt, context.lease_owner = job.attempt, lease_owner
        return run

    async def finalize_run(
        self,
        context: AgentRunObservationContext,
        *,
        status: AgentRunStatus,
        output: dict[str, Any],
        error: ContractError | None = None,
        validation_errors: list[dict[str, Any]] | None = None,
        token_count: int | None = None,
        cost_usd: Decimal | None = None,
        tool_calls: tuple[ToolCallObservation, ...] = (),
        completed_at: datetime | None = None,
    ) -> AgentRun:
        """Persist one terminal agent run and emit completion observability."""
        finished_at = completed_at or datetime.now(UTC)
        duration_ms = max(
            0,
            int((finished_at - context.started_at).total_seconds() * 1000),
        )
        run = await self.uow.session.scalar(
            select(AgentRun)
            .where(AgentRun.id == context.run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if run is not None:
            identity = {
                "job_id": context.correlation.job_id,
                "agent_id": context.correlation.agent_id,
                "agent_definition_id": context.agent_definition_id,
                "agent_definition_version": context.agent_definition_version,
                "prompt_version_id": context.prompt_version_id,
                "prompt_reference": context.prompt_reference,
                "prompt_sha256": context.prompt_sha256,
                "run_number": context.run_number,
                "model": context.model,
                "input_hash": context.input_hash,
                "started_at": context.started_at,
                "job_attempt": context.job_attempt,
                "lease_owner": context.lease_owner,
            }
            if any(getattr(run, key) != value for key, value in identity.items()):
                raise ValueError("agent run context identity mismatch")
            if run.status != "RUNNING":
                raise ValueError("agent run is already terminal")
        elif context.correlation.agent_id == "A07":
            raise ValueError("A07 requires a persisted started run")
        else:
            # Preserve the terminal-only observer contract for other agents.
            run = AgentRun(
                id=context.run_id,
                job_id=context.correlation.job_id,
                agent_definition_id=context.agent_definition_id,
                agent_id=context.correlation.agent_id,
                agent_definition_version=context.agent_definition_version,
                prompt_version_id=context.prompt_version_id,
                prompt_reference=context.prompt_reference,
                prompt_sha256=context.prompt_sha256,
                run_number=context.run_number,
                model=context.model,
                input_hash=context.input_hash,
                started_at=context.started_at,
            )
            self.uow.agent_runs.add(run)
        run.token_count = token_count
        run.cost_usd = cost_usd
        run.validation_errors = validation_errors
        run.status = status.value
        run.output = output
        run.error = error.model_dump() if error is not None else None
        run.completed_at = finished_at
        await self.uow.flush()

        for tool_call in tool_calls:
            self.uow.agent_tool_calls.add(
                AgentToolCall(
                    agent_run_id=run.id,
                    tool_id=tool_call.tool_id,
                    input_hash=tool_call.input_hash,
                    output_hash=tool_call.output_hash,
                    duration_ms=tool_call.duration_ms,
                )
            )
        if tool_calls:
            await self.uow.flush()

        emit_structured_log(
            sink=self.log_sink,
            level="INFO" if status == AgentRunStatus.SUCCESS else "ERROR",
            event_type="agent_run_completed",
            message="agent run completed",
            correlation=context.correlation,
            metadata={
                "status": status.value,
                "duration_ms": duration_ms,
                "token_count": token_count,
                "tool_call_count": len(tool_calls),
            },
        )
        with suppress(Exception):
            emit_agent_run_completed(
                self.telemetry,
                correlation=context.correlation,
                agent_run_id=run.id,
                prompt_reference=context.prompt_reference,
                run_number=context.run_number,
                model=context.model,
                status=status.value,
                duration_ms=duration_ms,
                token_count=token_count,
                cost_usd=cost_usd,
                tool_call_count=len(tool_calls),
            )
        return run


def _hash_payload(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    return hashlib.sha256(encoded).hexdigest()
