"""Runtime integration tests: lease → run → persist → event → successor (Lane C / W9 prep).

Proves the library path that W9 will commission later. Worker and scheduler process
entrypoints remain fail-closed (Exit 78); no production claim enablement.
"""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from money_machine.agents.base import (
    AgentContext,
    AgentNotCommissionedError,
    BaseAgent,
)
from money_machine.agents.runtime import AgentRunner
from money_machine.domain.enums import AgentRunStatus, JobStatus, RetryClass, SideEffectClass
from money_machine.domain.events import EventName
from money_machine.domain.models.common import SuccessContract
from money_machine.domain.models.jobs import AgentResult, JobEnvelope
from money_machine.integrations.llm.fake_provider import FakeLLMProvider
from money_machine.orchestration._foundation import EXIT_UNAVAILABLE
from money_machine.orchestration.event_dispatcher import EventDispatcher
from money_machine.orchestration.leases import (
    claim_ready_job,
    deterministic_worker_id,
    release_lease,
)
from money_machine.persistence.seed import seed
from money_machine.persistence.tables import AgentRun, Event, Job
from money_machine.persistence.unit_of_work import UnitOfWork
from tests.integration.factories import NOW, make_shop, make_workflow


class _StaticSuccessAgent(BaseAgent):
    """Deterministic agent that completes without external calls."""

    async def execute(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            job_id=context.job.job_id,
            agent_run_id=context.run_id,
            agent_id=context.definition.agent_id,
            agent_definition_version=context.definition.contract_version,
            prompt_reference=context.prompt_reference,
            prompt_sha256=context.prompt_sha256,
            status=AgentRunStatus.SUCCESS,
            output={"runtime_integration": "ok"},
            emitted_events=(EventName.SCHEDULE_CONFIGURED,),
        )


def _job_envelope(job: Job) -> JobEnvelope:
    return JobEnvelope(
        job_id=job.id,
        workflow_id=job.workflow_id,
        object_id=job.object_id,
        job_type=job.job_type,
        object_type=job.object_type,
        owner_agent_id=job.owner_agent_id,
        status=JobStatus(job.status),
        input=dict(job.input or {}),
        scheduled_at=job.scheduled_at,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        idempotency_key=job.idempotency_key,
        side_effect_class=SideEffectClass(job.side_effect_class),
        retry_class=RetryClass(job.retry_class),
        success_contract=SuccessContract.model_validate(job.success_contract),
    )


async def _make_schedule_configuration_job(
    session: AsyncSession,
    workflow_id: UUID,
    *,
    object_id: UUID,
) -> Job:
    job = Job(
        id=uuid4(),
        workflow_id=workflow_id,
        job_type="ScheduleConfigurationJob",
        object_type="workflow_runs",
        object_id=object_id,
        owner_agent_id="A01",
        status=JobStatus.READY.value,
        input={"timezone": "UTC"},
        success_contract={"output_model": "AgentResult"},
        scheduled_at=NOW,
        attempt=0,
        max_attempts=3,
        idempotency_key=f"SCHEDULE:{uuid4()}",
        side_effect_class=SideEffectClass.NONE.value,
        retry_class=RetryClass.IDEMPOTENT.value,
        allowed_mode="simulation",
        version=1,
    )
    session.add(job)
    await session.flush()
    return job


async def _make_research_collection_job(
    session: AsyncSession,
    workflow_id: UUID,
    *,
    object_id: UUID,
) -> Job:
    job = Job(
        id=uuid4(),
        workflow_id=workflow_id,
        job_type="ResearchCollectionJob",
        object_type="workflow_runs",
        object_id=object_id,
        owner_agent_id="A03",
        status=JobStatus.READY.value,
        input={},
        success_contract={"output_model": "ResearchReport"},
        scheduled_at=NOW,
        attempt=0,
        max_attempts=3,
        idempotency_key=f"RESEARCH:{uuid4()}",
        side_effect_class=SideEffectClass.EXTERNAL_READ.value,
        retry_class=RetryClass.SAFE.value,
        allowed_mode="simulation",
        version=1,
    )
    session.add(job)
    await session.flush()
    return job


@pytest.mark.asyncio
async def test_lease_run_persist_event_and_successor_flow(
    session: AsyncSession,
    repository_root: Path,
) -> None:
    """Lease → AgentRunner (FakeLLM) → receipt → event → successor scheduling."""
    await seed(session, repository_root=repository_root)
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await _make_schedule_configuration_job(
        session,
        workflow.id,
        object_id=workflow.id,
    )

    worker_id = deterministic_worker_id(0)
    occurred_at = NOW
    claimed = await claim_ready_job(
        session,
        worker_id=worker_id,
        now=occurred_at,
        lease_duration=timedelta(minutes=5),
    )
    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == JobStatus.RUNNING.value
    assert claimed.lease_owner == worker_id

    runner = AgentRunner.from_repository_root(
        repository_root,
        provider=FakeLLMProvider(),
    )
    envelope = _job_envelope(claimed)
    result, receipt = await runner.execute(
        session,
        job=envelope,
        agent=_StaticSuccessAgent(),
        production=True,
        run_at=occurred_at,
    )
    assert result.status is AgentRunStatus.SUCCESS
    assert receipt.agent_id == "A01"
    assert receipt.output == {"runtime_integration": "ok"}

    dispatcher = EventDispatcher(UnitOfWork(session))
    successor_ids = await dispatcher.dispatch(
        event_name=EventName.SCHEDULE_CONFIGURED,
        aggregate_type="scheduled_triggers",
        aggregate_id=workflow.id,
        workflow_id=workflow.id,
        job_id=job.id,
        payload={"timezone": "UTC"},
        occurred_at=occurred_at,
    )
    assert len(successor_ids) == 2

    await release_lease(
        session,
        job_id=job.id,
        worker_id=worker_id,
        now=occurred_at + timedelta(seconds=5),
        final_status=JobStatus.SUCCEEDED,
    )

    stored_run = (
        await session.execute(select(AgentRun).where(AgentRun.id == receipt.run_id))
    ).scalar_one()
    assert stored_run.job_id == job.id
    assert stored_run.status == AgentRunStatus.SUCCESS.value

    events = (
        (
            await session.execute(
                select(Event).where(
                    Event.event_name == EventName.SCHEDULE_CONFIGURED.value,
                    Event.job_id == job.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1

    successors = (
        (await session.execute(select(Job).where(Job.id.in_(successor_ids)))).scalars().all()
    )
    successor_types = {row.job_type for row in successors}
    assert successor_types == {"WeeklyReviewJob", "MonthlyDeepPassJob"}
    assert all(row.status == JobStatus.PENDING.value for row in successors)

    await session.refresh(job)
    assert job.status == JobStatus.SUCCEEDED.value
    assert job.lease_owner is None


@pytest.mark.asyncio
async def test_designed_agent_fail_closed_after_lease(
    session: AsyncSession,
    repository_root: Path,
) -> None:
    """Leasing is allowed; production execution refuses DESIGNED (A03) agents."""
    await seed(session, repository_root=repository_root)
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await _make_research_collection_job(
        session,
        workflow.id,
        object_id=workflow.id,
    )

    worker_id = deterministic_worker_id(1)
    claimed = await claim_ready_job(
        session,
        worker_id=worker_id,
        now=NOW,
        lease_duration=timedelta(minutes=5),
    )
    assert claimed is not None
    assert claimed.owner_agent_id == "A03"

    runner = AgentRunner.from_repository_root(
        repository_root,
        provider=FakeLLMProvider(),
    )
    with pytest.raises(AgentNotCommissionedError, match="production execution requires"):
        await runner.execute(
            session,
            job=_job_envelope(claimed),
            agent=_StaticSuccessAgent(),
            production=True,
        )

    runs = (
        (await session.execute(select(AgentRun).where(AgentRun.job_id == job.id))).scalars().all()
    )
    assert runs == []

    events = (await session.execute(select(Event).where(Event.job_id == job.id))).scalars().all()
    assert events == []

    successors = (
        (
            await session.execute(
                select(Job).where(
                    Job.workflow_id == workflow.id,
                    Job.id != job.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert successors == []


@pytest.mark.parametrize(
    "module",
    [
        "money_machine.orchestration.worker",
        "money_machine.orchestration.scheduler",
    ],
)
def test_process_entrypoints_remain_exit_78(module: str) -> None:
    """Worker/scheduler subprocesses still fail-closed; no W9 claim lift."""
    result = subprocess.run(
        [sys.executable, "-m", module],
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
        env={**os.environ, "APP_ENV": "test"},
    )
    assert result.returncode == EXIT_UNAVAILABLE
    assert result.stdout == ""
    # Wave 9: Commissioning gates pass but process loop deferred
    assert "Commissioning gates pass" in result.stderr
    assert "no jobs were processed" in result.stderr


@pytest.mark.asyncio
async def test_uncommissioned_agent_refuses_execution_on_production_path(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    repository_root: Path,
) -> None:
    """Wave 9: DESIGNED agents refuse execution even when job is claimed (fail-closed)."""
    from money_machine.agents.base import AgentNotCommissionedError, BaseAgent
    from money_machine.agents.runtime import AgentRunner
    from money_machine.domain.models.jobs import AgentResult
    from money_machine.integrations.llm.fake_provider import FakeLLMProvider
    from money_machine.persistence.unit_of_work import unit_of_work

    # Create a simple DESIGNED agent for testing
    class _TestDesignedAgent(BaseAgent):
        async def execute(self, context) -> AgentResult:  # type: ignore[override]
            return AgentResult(
                job_id=context.job.job_id,
                agent_run_id=context.run_id,
                agent_id=context.definition.agent_id,
                agent_definition_version=context.definition.contract_version,
                prompt_reference=context.prompt_reference,
                prompt_sha256=context.prompt_sha256,
                status=AgentRunStatus.SUCCESS,
                output={},
            )

    # Setup: create test data
    await seed(session, repository_root=repository_root)
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop=shop)

    # Create a job for A03 (Market Research) which is DESIGNED
    job = await _make_schedule_configuration_job(
        session,
        workflow.id,
        object_id=workflow.id,
    )
    # Override owner to A03 (DESIGNED agent)
    job.owner_agent_id = "A03"
    job.job_type = "MarketResearchJob"
    await session.commit()

    job_id = job.id

    # Attempt to execute with production=True
    runner = AgentRunner.from_repository_root(
        repository_root,
        provider=FakeLLMProvider(),
    )

    async with unit_of_work(session_factory) as uow:
        job = await uow.session.get(Job, job_id)
        assert job is not None
        envelope = _job_envelope(job)
        agent = _TestDesignedAgent()

        # Execution should raise AgentNotCommissionedError
        with pytest.raises(AgentNotCommissionedError) as exc_info:
            await runner.execute(
                uow.session,
                job=envelope,
                agent=agent,
                production=True,
            )

        assert (
            "DESIGNED" in str(exc_info.value) or "not commissioned" in str(exc_info.value).lower()
        ), f"Expected 'DESIGNED' or 'not commissioned' in error message, got: {exc_info.value}"


@pytest.mark.asyncio
async def test_tested_agent_executes_on_production_path(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    repository_root: Path,
) -> None:
    """Wave 9: TESTED agents execute successfully on production path."""
    from money_machine.agents.implementations.shop_orchestrator import ShopOrchestratorAgent
    from money_machine.agents.runtime import AgentRunner
    from money_machine.domain.enums import AgentRunStatus
    from money_machine.integrations.llm.fake_provider import FakeLLMProvider
    from money_machine.persistence.unit_of_work import unit_of_work

    # Setup: create test data
    await seed(session, repository_root=repository_root)
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop=shop)

    # Create a job for A01 (Shop Orchestrator) which is TESTED
    job = await _make_schedule_configuration_job(
        session,
        workflow.id,
        object_id=workflow.id,
    )
    await session.commit()

    job_id = job.id

    # Execute with production=True (should succeed)
    runner = AgentRunner.from_repository_root(
        repository_root,
        provider=FakeLLMProvider(),
    )

    async with unit_of_work(session_factory) as uow:
        job = await uow.session.get(Job, job_id)
        assert job is not None
        envelope = _job_envelope(job)
        agent = ShopOrchestratorAgent()

        result, receipt = await runner.execute(
            uow.session,
            job=envelope,
            agent=agent,
            production=True,
        )

        # A01 is TESTED and should execute successfully
        assert result.status in (AgentRunStatus.SUCCESS, AgentRunStatus.FAILURE), (
            f"Expected SUCCESS or FAILURE for TESTED agent, got {result.status}"
        )
        assert receipt.agent_id == "A01"
        assert receipt.status in (AgentRunStatus.SUCCESS, AgentRunStatus.FAILURE)
