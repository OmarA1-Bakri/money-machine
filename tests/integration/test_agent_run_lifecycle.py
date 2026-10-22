"""Durable run lifecycle uses synthetic A07 jobs and isolated PostgreSQL only."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from money_machine.agents.prompt_store import PromptStore
from money_machine.agents.registry import AgentRegistry
from money_machine.config.settings import TelemetryConfig
from money_machine.domain.enums import AgentRunStatus, JobStatus, RetryClass, SideEffectClass
from money_machine.domain.models.common import ContractError, SuccessContract
from money_machine.integrations.posthog.client import PostHogClient
from money_machine.observability.agent_runs import AgentRunObserver
from money_machine.observability.correlation import CorrelationContext
from money_machine.observability.logging import StructuredLogSink
from money_machine.persistence.tables import AgentDefinition, AgentRun, Job, PromptVersion
from money_machine.persistence.unit_of_work import UnitOfWork
from tests.integration.factories import make_job, make_shop, make_workflow


def observer(session: AsyncSession) -> AgentRunObserver:
    return AgentRunObserver(
        UnitOfWork(session),
        PostHogClient(config=TelemetryConfig(version=1, enabled=False, allowed_events=())),
        StructuredLogSink(capture=True),
    )


async def setup_run(session: AsyncSession):
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await make_job(
        session, workflow, status="RUNNING", idempotency_key=f"lifecycle:{uuid4()}"
    )
    job.owner_agent_id = "A07"
    job.lease_owner = "fixture-worker"
    job.lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)
    definition = AgentDefinition(
        agent_id="A07",
        name="Synthetic lifecycle builder",
        implementation_version=1,
        contract_version=1,
        default_side_effect_class="EXTERNAL_WRITE",
        default_retry_class="RECONCILE_FIRST",
        timeout_seconds=600,
        commissioning_state="DESIGNED",
        commissioning_evidence=[],
    )
    prompt = PromptVersion(
        prompt_reference="prompt://A07/synthetic-lifecycle",
        version=1,
        sha256="a" * 64,
        source_path="tests/integration/test_agent_run_lifecycle.py",
    )
    session.add_all([definition, prompt])
    await session.flush()
    active = observer(session)
    context = active.begin_run(
        correlation=CorrelationContext(job.id, "A07", workflow.id, attempt=job.attempt),
        agent_definition_id=definition.id,
        agent_definition_version=definition.contract_version,
        prompt_version_id=prompt.id,
        prompt_reference=prompt.prompt_reference,
        prompt_sha256=prompt.sha256,
        run_number=await active.next_run_number(job.id),
        model=None,
        input_payload={"kind": "synthetic lifecycle test"},
    )
    return job, active, context


async def test_start_is_visible_before_terminal_result(
    session_factory: async_sessionmaker[AsyncSession],
):
    async with session_factory() as session:
        job, active, context = await setup_run(session)
        await active.persist_started_run(context, lease_owner="fixture-worker")
        await session.commit()
        job_id, run_id = job.id, context.run_id
    async with session_factory() as read:
        run = await read.get(AgentRun, run_id)
        assert run is not None
        assert (run.job_id, run.agent_id, run.status) == (job_id, "A07", "RUNNING")
        assert run.completed_at is None and run.error is None and run.output == {}
        assert run.prompt_sha256 == context.prompt_sha256
        assert run.input_hash == context.input_hash
        # Restart can finalize the same durable row, without inventing another run.
        terminal = await observer(read).finalize_run(
            context,
            status=AgentRunStatus.FAILURE,
            output={},
            error=ContractError(code="FIXTURE_INTERRUPTED", message="synthetic failure"),
        )
        await read.commit()
        assert terminal.id == run_id and terminal.completed_at is not None
    async with session_factory() as verify:
        rows = (await verify.scalars(select(AgentRun).where(AgentRun.job_id == job_id))).all()
        assert len(rows) == 1 and rows[0].status == "FAILURE"


async def test_unresolved_restart_and_terminal_replay_are_refused(session_factory):
    async with session_factory() as session:
        job, active, context = await setup_run(session)
        await active.persist_started_run(context, lease_owner="fixture-worker")
        await session.commit()
        job_id = job.id
    async with session_factory() as restarted:
        active = observer(restarted)
        # Reusing the old context cannot claim a fresh execution.
        with pytest.raises(ValueError, match=r"active|started|running"):
            await active.persist_started_run(context, lease_owner="fixture-worker")
        await restarted.rollback()
        await active.finalize_run(context, status=AgentRunStatus.SUCCESS, output={"test": True})
        await restarted.commit()
        with pytest.raises(ValueError, match="terminal"):
            await active.finalize_run(
                context,
                status=AgentRunStatus.FAILURE,
                output={},
                error=ContractError(code="BAD_REPLAY", message="must not replace success"),
            )
        await restarted.rollback()
        rows = (await restarted.scalars(select(AgentRun).where(AgentRun.job_id == job_id))).all()
        assert len(rows) == 1 and rows[0].status == "SUCCESS"


async def test_identity_change_cannot_finalize_another_run(session_factory):
    from dataclasses import replace

    async with session_factory() as session:
        _, active, context = await setup_run(session)
        await active.persist_started_run(context, lease_owner="fixture-worker")
        await session.commit()
        wrong = replace(context, input_hash="f" * 64)
        with pytest.raises(ValueError, match="identity"):
            await active.finalize_run(wrong, status=AgentRunStatus.SUCCESS, output={})
        await session.rollback()
        run = await session.get(AgentRun, context.run_id)
        assert run.status == "RUNNING" and run.completed_at is None


async def test_concurrent_starts_keep_one_unresolved_execution(session_factory):
    import asyncio
    from dataclasses import replace

    async with session_factory() as session:
        _, _, context = await setup_run(session)
        await session.commit()

    async def attempt(candidate):
        async with session_factory() as session:
            try:
                await observer(session).persist_started_run(candidate, lease_owner="fixture-worker")
                await session.commit()
                return True
            except ValueError:
                await session.rollback()
                return False

    outcomes = await asyncio.gather(attempt(context), attempt(replace(context, run_id=uuid4())))
    assert sorted(outcomes) == [False, True]
    async with session_factory() as session:
        rows = (
            await session.scalars(
                select(AgentRun).where(AgentRun.job_id == context.correlation.job_id)
            )
        ).all()
        assert len(rows) == 1 and rows[0].status == "RUNNING"


@pytest.mark.parametrize(
    "outcome", ["success", "failure", "cancelled", "wrong_run", "wrong_agent", "wrong_prompt"]
)
async def test_runner_commits_actual_a07_identity_before_execution(
    session_factory, repository_root, tmp_path, outcome
):
    import asyncio

    from money_machine.agents.base import AgentRegistryError, BaseAgent
    from money_machine.agents.runtime import AgentRunner
    from money_machine.domain.models.jobs import AgentResult, JobEnvelope
    from money_machine.integrations.llm.fake_provider import FakeLLMProvider
    from money_machine.persistence.seed import seed

    async with session_factory() as session:
        await seed(session, repository_root=repository_root)
        # A hash-verified synthetic PromptStore fixture; no production prompt claim.
        from hashlib import sha256

        from money_machine.persistence.tables import PromptVersion

        source = tmp_path / "prompts/agents/A07/v1.md"
        source.parent.mkdir(parents=True)
        source.write_text(
            "# Synthetic lifecycle test\n\n## Purpose\nTest only.\n"
            "\n## Input Contract\nJobEnvelope.\n\n## Output Contract\nAgentResult.\n"
            "\n## Instructions\nReturn a synthetic result.\n"
            "\n## Tool Permissions\nNo external tools.\n"
        )
        session.add(
            PromptVersion(
                prompt_reference="agent://A07/system/v1",
                version=1,
                sha256=sha256(source.read_bytes()).hexdigest(),
                source_path="synthetic-fixture/prompts/agents/A07/v1.md",
            )
        )
        await session.flush()
        shop = await make_shop(session)
        workflow = await make_workflow(session, shop)
        job = await make_job(
            session, workflow, status="RUNNING", idempotency_key=f"runner-lifecycle:{uuid4()}"
        )
        job.owner_agent_id, job.job_type = "A07", "BuildRepairJob"
        job.lease_owner = "fixture-runner"
        job.lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)
        await session.flush()
        envelope = JobEnvelope(
            job_id=job.id,
            workflow_id=workflow.id,
            object_id=job.object_id,
            job_type=job.job_type,
            object_type=job.object_type,
            owner_agent_id="A07",
            status=JobStatus.RUNNING,
            input=job.input,
            scheduled_at=job.scheduled_at,
            attempt=job.attempt,
            max_attempts=job.max_attempts,
            idempotency_key=job.idempotency_key,
            side_effect_class=SideEffectClass(job.side_effect_class),
            retry_class=RetryClass(job.retry_class),
            success_contract=SuccessContract(output_model="AgentResult"),
        )
        seen = []

        class ProbeAgent(BaseAgent):
            async def execute(self, context):
                async with session_factory() as read:
                    row = await read.get(AgentRun, context.run_id)
                    assert row.status == "RUNNING" and row.completed_at is None
                    assert row.job_id == context.job.job_id and row.agent_id == "A07"
                    assert row.prompt_reference == context.prompt_reference
                    assert row.prompt_sha256 == context.prompt_sha256
                    seen.append(row.id)
                if outcome == "failure":
                    raise RuntimeError("synthetic agent error")
                if outcome == "cancelled":
                    raise asyncio.CancelledError()
                return AgentResult(
                    job_id=context.job.job_id,
                    agent_run_id=uuid4() if outcome == "wrong_run" else context.run_id,
                    agent_id="A06" if outcome == "wrong_agent" else "A07",
                    agent_definition_version=context.definition.contract_version,
                    prompt_reference=context.prompt_reference,
                    prompt_sha256="b" * 64 if outcome == "wrong_prompt" else context.prompt_sha256,
                    status=AgentRunStatus.SUCCESS,
                    output={"test": True},
                )

        active = observer(session)
        runner = AgentRunner(
            registry=AgentRegistry.from_yaml(repository_root),
            prompt_store=PromptStore(tmp_path),
            provider=FakeLLMProvider(),
            observer=active,
        )
        if outcome == "cancelled":
            with pytest.raises(asyncio.CancelledError):
                await runner.execute(
                    session,
                    job=envelope,
                    agent=ProbeAgent(),
                    production=False,
                    lease_owner="fixture-runner",
                )
            await session.rollback()
            with pytest.raises(ValueError, match="unresolved active"):
                await runner.execute(
                    session,
                    job=envelope,
                    agent=ProbeAgent(),
                    production=False,
                    lease_owner="fixture-runner",
                )
        elif outcome.startswith("wrong_"):
            with pytest.raises(AgentRegistryError):
                await runner.execute(
                    session,
                    job=envelope,
                    agent=ProbeAgent(),
                    production=False,
                    lease_owner="fixture-runner",
                )
        else:
            result, receipt = await runner.execute(
                session,
                job=envelope,
                agent=ProbeAgent(),
                production=False,
                lease_owner="fixture-runner",
            )
            assert result.agent_run_id == receipt.run_id == seen[0]
        await session.rollback()
        assert len(seen) == 1
        async with session_factory() as read:
            row = await read.get(AgentRun, seen[0])
            expected = (
                "RUNNING"
                if outcome == "cancelled"
                else ("SUCCESS" if outcome == "success" else "FAILURE")
            )
            assert row.status == expected
            assert (row.completed_at is None) == (outcome == "cancelled")
        if outcome != "cancelled":
            assert all(record["agent_run_id"] == str(seen[0]) for record in active.log_sink.records)


@pytest.mark.parametrize("change", ["cancel", "attempt", "lease"])
async def test_start_refreshes_cached_job_under_lock(session_factory, change):

    async with session_factory() as cached:
        job, active, context = await setup_run(cached)
        await cached.commit()
        async with session_factory() as other:
            current = await other.get(Job, job.id)
            if change == "cancel":
                current.status = "CANCELLED"
            elif change == "attempt":
                current.attempt += 1
            else:
                current.lease_owner = "new-worker"
            await other.commit()
        with pytest.raises(ValueError, match="matching running job and lease"):
            await active.persist_started_run(context, lease_owner="fixture-worker")
        await cached.rollback()
        assert list(await cached.scalars(select(AgentRun))) == []


async def test_explicit_transaction_is_refused_without_committing_caller(
    session_factory, repository_root
):
    from sqlalchemy import text

    from money_machine.agents.base import AgentRegistryError, BaseAgent
    from money_machine.agents.runtime import AgentRunner
    from money_machine.integrations.llm.fake_provider import FakeLLMProvider

    class UncalledAgent(BaseAgent):
        async def execute(self, context):
            raise AssertionError("must not execute")

    runner = AgentRunner.from_repository_root(repository_root, provider=FakeLLMProvider())
    async with session_factory() as session, session.begin():
        job_row, _, _ = await setup_run(session)
        from money_machine.domain.models.jobs import JobEnvelope

        job = JobEnvelope(
            job_id=job_row.id,
            workflow_id=job_row.workflow_id,
            object_id=job_row.object_id,
            job_type=job_row.job_type,
            object_type=job_row.object_type,
            owner_agent_id="A07",
            status=JobStatus.RUNNING,
            input=job_row.input,
            scheduled_at=job_row.scheduled_at,
            attempt=job_row.attempt,
            max_attempts=job_row.max_attempts,
            idempotency_key=job_row.idempotency_key,
            side_effect_class=SideEffectClass(job_row.side_effect_class),
            retry_class=RetryClass(job_row.retry_class),
            success_contract=SuccessContract(output_model="AgentResult"),
        )
        with pytest.raises(AgentRegistryError, match="dedicated implicit-transaction"):
            await runner.execute(
                session,
                job=job,
                agent=UncalledAgent(),
                production=False,
                lease_owner="fixture-worker",
            )
        assert await session.scalar(text("SELECT 1")) == 1
        assert list(await session.scalars(select(AgentRun))) == []


async def test_a07_cannot_insert_a_terminal_run_without_its_start(session_factory):
    async with session_factory() as session:
        _, active, context = await setup_run(session)
        with pytest.raises(ValueError, match="persisted started run"):
            await active.finalize_run(context, status=AgentRunStatus.SUCCESS, output={})
        assert list(await session.scalars(select(AgentRun))) == []


@pytest.mark.parametrize(
    "invalid",
    ["running_completed", "running_output", "terminal_incomplete", "failure_without_error"],
)
async def test_database_enforces_active_and_terminal_shapes(session_factory, invalid):
    from sqlalchemy.exc import IntegrityError

    async with session_factory() as session:
        _, active, context = await setup_run(session)
        run = await active.persist_started_run(context, lease_owner="fixture-worker")
        await session.commit()
        if invalid == "running_completed":
            run.completed_at = datetime.now(UTC)
        elif invalid == "running_output":
            run.output = {"fake": "success"}
        elif invalid == "terminal_incomplete":
            run.status = "SUCCESS"
        else:
            run.status, run.completed_at = "FAILURE", datetime.now(UTC)
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()
        kept = await session.get(AgentRun, context.run_id)
        assert kept.status == "RUNNING" and kept.completed_at is None


async def test_lifecycle_migration_preserves_terminal_history_and_refuses_unresolved_downgrade(
    session_factory, migrated_url, repository_root
):
    import asyncio

    from tests.integration.alembic_support import downgrade, upgrade

    async with session_factory() as session:
        _, active, context = await setup_run(session)
        await active.persist_started_run(context, lease_owner="fixture-worker")
        await session.commit()
    with pytest.raises(RuntimeError, match="remain RUNNING"):
        await asyncio.to_thread(downgrade, migrated_url, repository_root, "b2c3d4e5f6a7")
    async with session_factory() as session:
        active = observer(session)
        run = await active.finalize_run(
            context, status=AgentRunStatus.SUCCESS, output={"test": True}
        )
        await session.commit()
        before = (run.id, run.started_at, run.completed_at, run.prompt_sha256, run.output)
    await asyncio.to_thread(downgrade, migrated_url, repository_root, "b2c3d4e5f6a7")
    await asyncio.to_thread(upgrade, migrated_url, repository_root)
    async with session_factory() as session:
        run = await session.get(AgentRun, context.run_id)
        assert (run.id, run.started_at, run.completed_at, run.prompt_sha256, run.output) == before
        assert run.status == "SUCCESS"
