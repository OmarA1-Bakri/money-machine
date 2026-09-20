"""Integration tests for AgentRunner receipts and commissioning gates."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.agents.base import (
    AgentContext,
    AgentDefinition,
    AgentNotCommissionedError,
    BaseAgent,
)
from money_machine.agents.prompt_store import PromptStore
from money_machine.agents.registry import AgentRegistry
from money_machine.agents.runtime import AgentRunner
from money_machine.config.settings import AgentCommissioningState
from money_machine.domain.enums import AgentRunStatus, JobStatus, RetryClass, SideEffectClass
from money_machine.domain.models.common import SuccessContract
from money_machine.domain.models.jobs import AgentResult, JobEnvelope
from money_machine.integrations.llm.fake_provider import FakeLLMProvider
from money_machine.persistence.seed import seed
from money_machine.persistence.tables import AgentRun
from tests.integration.factories import NOW, make_job, make_shop, make_workflow


class _StaticSuccessAgent(BaseAgent):
    async def execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            job_id=context.job.job_id,
            agent_run_id=context.run_id,
            agent_id=context.definition.agent_id,
            agent_definition_version=context.definition.contract_version,
            prompt_reference=context.prompt_reference,
            prompt_sha256=context.prompt_sha256,
            status=AgentRunStatus.SUCCESS,
            output={"receipt": "ok"},
        )


def _tested_registry(base: AgentRegistry) -> AgentRegistry:
    tested = {
        agent_id: AgentDefinition(
            agent_id=definition.agent_id,
            name=definition.name,
            contract_version=definition.contract_version,
            system_prompt_reference=definition.system_prompt_reference,
            input_contracts=definition.input_contracts,
            output_contracts=definition.output_contracts,
            allowed_tools=definition.allowed_tools,
            default_side_effect_class=definition.default_side_effect_class,
            timeout_seconds=definition.timeout_seconds,
            commissioning_state=(
                AgentCommissioningState.TESTED
                if definition.agent_id == "A01"
                else definition.commissioning_state
            ),
            commissioning_evidence=definition.commissioning_evidence,
        )
        for agent_id, definition in {item.agent_id: item for item in base.roster()}.items()
    }
    return AgentRegistry(tested)


def _job_envelope(job_id: object, workflow_id: object, object_id: object) -> JobEnvelope:
    return JobEnvelope(
        job_id=job_id,  # type: ignore[arg-type]
        workflow_id=workflow_id,  # type: ignore[arg-type]
        object_id=object_id,  # type: ignore[arg-type]
        job_type="BootstrapRecordsJob",
        object_type="workflow_runs",
        owner_agent_id="A01",
        status=JobStatus.READY,
        input={"shop_id": str(object_id)},
        scheduled_at=NOW,
        attempt=0,
        max_attempts=3,
        idempotency_key=f"BOOTSTRAP:{uuid4()}",
        side_effect_class=SideEffectClass.NONE,
        retry_class=RetryClass.SAFE,
        success_contract=SuccessContract(output_model="AgentResult"),
    )


@pytest.mark.asyncio
async def test_runner_persists_run_receipt(
    session: AsyncSession,
    repository_root: Path,
) -> None:
    await seed(session, repository_root=repository_root)
    await session.flush()

    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await make_job(
        session,
        workflow,
        status="READY",
        idempotency_key=f"BOOTSTRAP:{uuid4()}",
    )
    job.owner_agent_id = "A01"
    await session.flush()

    base_registry = AgentRegistry.from_yaml(repository_root)
    runner = AgentRunner(
        registry=_tested_registry(base_registry),
        prompt_store=PromptStore(repository_root),
        provider=FakeLLMProvider(),
    )

    envelope = _job_envelope(job.id, workflow.id, workflow.id)
    result, receipt = await runner.execute(
        session,
        job=envelope,
        agent=_StaticSuccessAgent(),
        production=True,
        run_at=datetime(2026, 9, 20, 12, 0, tzinfo=UTC),
    )

    assert result.status is AgentRunStatus.SUCCESS
    assert receipt.run_id == result.agent_run_id
    assert receipt.agent_id == "A01"
    assert receipt.output == {"receipt": "ok"}

    stored = (
        await session.execute(select(AgentRun).where(AgentRun.id == receipt.run_id))
    ).scalar_one()
    assert stored.job_id == job.id
    assert stored.agent_id == "A01"
    assert stored.status == "SUCCESS"
    assert stored.output == {"receipt": "ok"}
    assert stored.error is None
    assert stored.prompt_reference == "agent://A01/system/v1"
    assert len(stored.prompt_sha256) == 64


@pytest.mark.asyncio
async def test_runner_fail_closed_for_uncommissioned_production_job(
    session: AsyncSession,
    repository_root: Path,
) -> None:
    await seed(session, repository_root=repository_root)
    await session.flush()

    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await make_job(session, workflow, status="READY")
    job.owner_agent_id = "A03"
    await session.flush()

    runner = AgentRunner.from_repository_root(
        repository_root,
        provider=FakeLLMProvider(),
    )
    envelope = _job_envelope(job.id, workflow.id, workflow.id)
    envelope = envelope.model_copy(update={"owner_agent_id": "A03"})

    with pytest.raises(AgentNotCommissionedError, match="production execution requires"):
        await runner.execute(
            session,
            job=envelope,
            agent=_StaticSuccessAgent(),
            production=True,
        )

    statement = select(AgentRun).where(AgentRun.job_id == job.id)
    runs = (await session.execute(statement)).scalars().all()
    assert runs == []
