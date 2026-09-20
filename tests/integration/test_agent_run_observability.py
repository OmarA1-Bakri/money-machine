"""Integration tests for agent-run observability persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.config.settings import TelemetryConfig
from money_machine.domain.enums import AgentRunStatus
from money_machine.domain.events import TelemetryEventName
from money_machine.integrations.posthog.client import PostHogClient
from money_machine.observability.agent_runs import AgentRunObserver, ToolCallObservation
from money_machine.observability.correlation import CorrelationContext
from money_machine.observability.logging import StructuredLogSink
from money_machine.persistence.unit_of_work import UnitOfWork
from tests.integration.factories import make_job, make_shop, make_workflow


class TestAgentRunObservability:
    """Prove agent runs, tool calls, logs, and telemetry queue correctly."""

    async def test_finalize_run_persists_observability_fields(
        self, session: AsyncSession
    ) -> None:
        """Completed runs persist metrics, tool calls, logs, and PostHog-shaped events."""
        shop = await make_shop(session)
        workflow = await make_workflow(session, shop)
        job = await make_job(session, workflow)

        definition = await _seed_agent_definition(session, agent_id="A01")
        prompt = await _seed_prompt_version(session, agent_id="A01")

        telemetry = PostHogClient(
            config=TelemetryConfig(
                version=1,
                enabled=True,
                allowed_events=(
                    TelemetryEventName.AGENT_RUN_STARTED,
                    TelemetryEventName.AGENT_RUN_COMPLETED,
                ),
            )
        )
        log_sink = StructuredLogSink(capture=True)
        uow = UnitOfWork(session)
        observer = AgentRunObserver(uow=uow, telemetry=telemetry, log_sink=log_sink)

        correlation = CorrelationContext(
            job_id=job.id,
            agent_id="A01",
            workflow_id=workflow.id,
            job_type=job.job_type,
            attempt=job.attempt,
        )
        context = observer.begin_run(
            correlation=correlation,
            agent_definition_id=definition.id,
            agent_definition_version=definition.contract_version,
            prompt_version_id=prompt.id,
            prompt_reference=prompt.prompt_reference,
            prompt_sha256=prompt.sha256,
            run_number=await observer.next_run_number(job.id),
            model="fake-model",
            input_payload={"query": "test"},
        )

        started_at = datetime.now(UTC) - timedelta(seconds=2)
        context.started_at = started_at

        run = await observer.finalize_run(
            context,
            status=AgentRunStatus.SUCCESS,
            output={"result": "ok"},
            token_count=128,
            cost_usd=Decimal("0.0025"),
            tool_calls=(
                ToolCallObservation(
                    tool_id="search_market",
                    input_payload={"term": "planner"},
                    output_payload={"hits": 3},
                    duration_ms=120,
                ),
            ),
            completed_at=datetime.now(UTC),
        )

        assert run.model == "fake-model"
        assert run.input_hash is not None
        assert len(run.input_hash) == 64
        assert run.token_count == 128
        assert run.cost_usd == Decimal("0.0025")
        assert run.run_number == 1

        tool_calls = await uow.agent_tool_calls.for_run(run.id)
        assert len(tool_calls) == 1
        assert tool_calls[0].tool_id == "search_market"
        assert tool_calls[0].duration_ms == 120

        assert any(record["event_type"] == "agent_run_started" for record in log_sink.records)
        assert any(record["event_type"] == "agent_run_completed" for record in log_sink.records)

        queued = telemetry.drain()
        assert [event["event"] for event in queued] == [
            "agent_run_started",
            "agent_run_completed",
        ]
        completed = queued[1]
        assert completed["properties"]["status"] == "SUCCESS"
        assert completed["properties"]["token_count"] == 128
        assert completed["properties"]["tool_call_count"] == 1

    async def test_failed_run_persists_structured_error(self, session: AsyncSession) -> None:
        """Failure runs store structured errors and still emit completion telemetry."""
        from money_machine.domain.models.common import ContractError

        shop = await make_shop(session)
        workflow = await make_workflow(session, shop)
        job = await make_job(session, workflow)
        definition = await _seed_agent_definition(session, agent_id="A02")
        prompt = await _seed_prompt_version(session, agent_id="A02")

        telemetry = PostHogClient(
            config=TelemetryConfig(
                version=1,
                enabled=True,
                allowed_events=(
                    TelemetryEventName.AGENT_RUN_STARTED,
                    TelemetryEventName.AGENT_RUN_COMPLETED,
                ),
            )
        )
        uow = UnitOfWork(session)
        observer = AgentRunObserver(
            uow=uow,
            telemetry=telemetry,
            log_sink=StructuredLogSink(capture=True),
        )

        context = observer.begin_run(
            correlation=CorrelationContext(job_id=job.id, agent_id="A02"),
            agent_definition_id=definition.id,
            agent_definition_version=definition.contract_version,
            prompt_version_id=prompt.id,
            prompt_reference=prompt.prompt_reference,
            prompt_sha256=prompt.sha256,
            run_number=1,
            model="fake-model",
            input_payload={"check": "credentials"},
        )

        run = await observer.finalize_run(
            context,
            status=AgentRunStatus.FAILURE,
            output={},
            error=ContractError(code="SCHEMA_VALIDATION", message="invalid output"),
            validation_errors=[{"field": "title", "issue": "required"}],
        )

        assert run.status == "FAILURE"
        assert run.error == {
            "code": "SCHEMA_VALIDATION",
            "message": "invalid output",
            "retryable": False,
            "blocker_action": None,
            "safe_detail": {},
        }
        assert run.validation_errors == [{"field": "title", "issue": "required"}]


async def _seed_agent_definition(session: AsyncSession, *, agent_id: str):
    from money_machine.persistence.tables import AgentDefinition

    definition = AgentDefinition(
        id=uuid4(),
        agent_id=agent_id,
        name=f"Agent {agent_id}",
        implementation_version=1,
        contract_version=1,
        default_side_effect_class="READ_ONLY",
        default_retry_class="SAFE",
        timeout_seconds=600,
        commissioning_state="TESTED",
        commissioning_evidence=[{"kind": "integration_test"}],
    )
    session.add(definition)
    await session.flush()
    return definition


async def _seed_prompt_version(session: AsyncSession, *, agent_id: str):
    from money_machine.persistence.tables import PromptVersion

    prompt = PromptVersion(
        id=uuid4(),
        prompt_reference=f"prompt://{agent_id}/system",
        version=1,
        sha256="a" * 64,
        source_path=f"prompts/agents/{agent_id}/v1.md",
    )
    session.add(prompt)
    await session.flush()
    return prompt
