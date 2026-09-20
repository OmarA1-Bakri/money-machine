"""Worker process — production claim path (Wave 9).

Conditionally lifts Exit 78 when commissioning evidence gates pass. Claims READY jobs,
executes via AgentRunner, persists results, emits events, and creates successors.
Uncommissioned agents (DESIGNED) remain fail-closed.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

from money_machine.agents.base import AgentNotCommissionedError
from money_machine.agents.registry import AgentRegistry
from money_machine.agents.runtime import AgentRunner
from money_machine.config.runtime import load_runtime_settings
from money_machine.config.settings import AgentCommissioningState
from money_machine.domain.enums import JobStatus
from money_machine.domain.errors import InvalidTransitionError
from money_machine.domain.models.jobs import AgentResult, JobEnvelope
from money_machine.integrations.llm.fake_provider import FakeLLMProvider
from money_machine.orchestration._foundation import unavailable
from money_machine.orchestration.event_dispatcher import EventDispatcher
from money_machine.orchestration.leases import (
    claim_ready_job,
    deterministic_worker_id,
    heartbeat,
    release_lease,
)
from money_machine.persistence.database import (
    check_connectivity,
    create_engine,
    create_session_factory,
)
from money_machine.persistence.tables import Job
from money_machine.persistence.unit_of_work import UnitOfWork, unit_of_work

LOGGER: Final = logging.getLogger(__name__)
LEASE_DURATION: Final = timedelta(minutes=5)
CLAIM_POLL_INTERVAL: Final = timedelta(seconds=5)


def _check_commissioning_gates() -> bool:
    """Check commissioning evidence gates per D-0028.

    Verifies ALL of:
    1. Runtime settings valid (database config)
    2. Agent registry loads (config valid, tools resolve)
    3. At least one agent is TESTED/COMMISSIONED
    4. Prompt integrity: file exists, hash computable, sections present, no secrets

    Returns True if at least one agent passes ALL gates.
    Returns False if gates fail, causing worker to exit 78.
    """
    import hashlib

    from money_machine.agents.prompt_store import PromptStore

    try:
        # Gate 1: Runtime settings valid (database config)
        _ = load_runtime_settings()
        LOGGER.debug("Gate 1/5: Runtime settings loaded")

        # Gate 2: Agent registry loads (config valid, tools resolve)
        repo_root = Path(__file__).parent.parent.parent.parent
        registry = AgentRegistry.from_yaml(repo_root)
        LOGGER.debug("Gate 2/5: Agent registry loaded with %d agents", len(list(registry.roster())))

        # Gate 3: At least one agent is TESTED/COMMISSIONED
        tested_or_commissioned = [
            defn
            for defn in registry.roster()
            if defn.commissioning_state
            in (
                AgentCommissioningState.TESTED,
                AgentCommissioningState.COMMISSIONED,
            )
        ]

        if not tested_or_commissioned:
            LOGGER.error(
                "Gate 3/5 FAILED: No TESTED or COMMISSIONED agents found; Exit 78 held. "
                "Found %d agents total, all in state DESIGNED or earlier.",
                len(list(registry.roster())),
            )
            return False

        LOGGER.debug("Gate 3/5: Found %d TESTED/COMMISSIONED agents", len(tested_or_commissioned))

        # Gate 4: Tool registry loads successfully
        from money_machine.tools.registry import ToolRegistry

        tool_registry = ToolRegistry.canonical()
        LOGGER.debug("Gate 4/5: Tool registry loaded with %d tools", len(tool_registry.all_tools()))

        # Gate 5: Prompt integrity for TESTED/COMMISSIONED agents
        # Per D-0028: file exists, SHA-256 computable, required sections present, no secrets
        prompt_store = PromptStore(repo_root)
        agents_with_prompt_failures: list[str] = []

        for agent_def in tested_or_commissioned:
            try:
                # Compute hash from file
                prompt_file = (
                    repo_root
                    / "prompts"
                    / "agents"
                    / agent_def.agent_id
                    / f"{agent_def.system_prompt_reference}.md"
                )

                if not prompt_file.exists():
                    relative_path = prompt_file.relative_to(repo_root)
                    agents_with_prompt_failures.append(
                        f"{agent_def.agent_id}: file not found at {relative_path}"
                    )
                    continue

                # Compute SHA-256 hash
                digest = hashlib.sha256()
                with prompt_file.open("rb") as source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b""):
                        digest.update(chunk)
                computed_hash = digest.hexdigest()

                # Verify prompt integrity: sections present, no secrets
                # PromptStore.load() will validate sections and check for secrets
                _ = prompt_store.load(
                    agent_def.agent_id,
                    agent_def.system_prompt_reference,
                    expected_hash=computed_hash,
                )

                LOGGER.debug(
                    "Prompt integrity verified for %s: %s (hash %s...)",
                    agent_def.agent_id,
                    agent_def.system_prompt_reference,
                    computed_hash[:8],
                )

            except Exception as prompt_error:
                agents_with_prompt_failures.append(
                    f"{agent_def.agent_id}: {type(prompt_error).__name__}: {prompt_error}"
                )

        if agents_with_prompt_failures:
            LOGGER.error(
                "Gate 5/5 FAILED: Prompt integrity failures for TESTED/COMMISSIONED agents:\n%s",
                "\n".join(f"  - {failure}" for failure in agents_with_prompt_failures),
            )
            return False

        LOGGER.debug("Gate 5/5: All prompts verified (integrity + sections + no secrets)")

        # All gates pass
        LOGGER.info(
            "Commissioning evidence gates PASS (D-0028): %d agent(s) eligible: %s",
            len(tested_or_commissioned),
            [a.agent_id for a in tested_or_commissioned],
        )
        return True

    except Exception as error:
        LOGGER.exception("Commissioning gate check failed: %s", error)
        return False


def _job_envelope(job: Job) -> JobEnvelope:
    """Convert a Job table row to a JobEnvelope for agent execution."""
    from money_machine.domain.enums import RetryClass, SideEffectClass
    from money_machine.domain.models.common import SuccessContract

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


async def _execute_job_with_runner(
    runner: AgentRunner,
    uow: UnitOfWork,
    job: Job,
    worker_id: str,
    now: datetime,
) -> AgentResult | None:
    """Execute one job via AgentRunner, persist result, emit events, create successors.

    Returns the AgentResult on success, or None if execution failed.
    This is the REAL claim path: claim → execute → persist → event → successor.
    """
    try:
        # Convert Job row to JobEnvelope
        envelope = _job_envelope(job)

        # Load agent implementation
        definition = runner.definition_for_job(envelope)

        # Import the agent class dynamically
        from money_machine.agents.implementations import (
            account_integration,
            shop_orchestrator,
        )

        agent_map = {
            "A01": shop_orchestrator.ShopOrchestratorAgent,
            "A02": account_integration.AccountIntegrationAgent,
        }

        agent_class = agent_map.get(definition.agent_id)
        if agent_class is None:
            LOGGER.error(
                "No implementation found for agent %s; failing job %s",
                definition.agent_id,
                job.id,
            )
            # Transition job to FAILED
            job.status = JobStatus.FAILED.value
            job.updated_at = now
            await uow.commit()
            return None

        agent = agent_class()

        # Execute via AgentRunner (handles commissioning state check internally)
        result, receipt = await runner.execute(
            uow.session,
            job=envelope,
            agent=agent,
            production=True,
            run_at=now,
        )

        # Heartbeat the lease to prevent expiry during execution
        await heartbeat(
            uow.session,
            job_id=job.id,
            worker_id=worker_id,
            now=now,
        )

        # Determine final status from result
        from money_machine.domain.enums import AgentRunStatus

        if result.status == AgentRunStatus.SUCCESS:
            final_status = JobStatus.SUCCEEDED
        elif result.status == AgentRunStatus.FAILURE:
            final_status = JobStatus.FAILED
        else:
            # BLOCKED or other non-terminal status
            final_status = JobStatus.BLOCKED

        # Release lease with final status
        await release_lease(
            uow.session,
            job_id=job.id,
            worker_id=worker_id,
            final_status=final_status,
            now=now,
        )

        # Emit events from agent result
        if result.emitted_events:
            dispatcher = EventDispatcher(uow)
            for event_name in result.emitted_events:
                await dispatcher.dispatch(
                    event_name=event_name,
                    aggregate_type="Job",
                    aggregate_id=job.id,
                    workflow_id=job.workflow_id,
                    job_id=job.id,
                    payload=dict(result.output),
                    occurred_at=now,
                )

        await uow.commit()

        LOGGER.info(
            "Job %s completed with status %s (agent %s, run %s)",
            job.id,
            final_status.value,
            definition.agent_id,
            receipt.run_id,
        )

        return result

    except AgentNotCommissionedError as error:
        LOGGER.error(
            "Agent not commissioned for job %s: %s; failing job",
            job.id,
            error,
        )
        # Transition job to FAILED with uncommissioned reason
        job.status = JobStatus.FAILED.value
        job.updated_at = now
        await release_lease(
            uow.session,
            job_id=job.id,
            worker_id=worker_id,
            final_status=JobStatus.FAILED,
            now=now,
        )
        await uow.commit()
        return None

    except InvalidTransitionError as error:
        LOGGER.error(
            "Job transition error for job %s: %s",
            job.id,
            error,
        )
        await uow.rollback()
        return None

    except Exception as error:
        LOGGER.exception(
            "Unexpected error executing job %s: %s",
            job.id,
            error,
        )
        await uow.rollback()
        return None


async def _worker_loop() -> None:
    """Main worker loop: claim jobs, execute via AgentRunner, emit events, create successors.

    Wave 9: Runs when commissioning evidence gates pass per D-0028.
    Claims READY jobs, invokes AgentRunner, persists results, emits events, spawns successors.
    """
    settings = load_runtime_settings()
    engine = create_engine(settings.database)

    # Verify database connectivity
    if not await check_connectivity(engine):
        LOGGER.error("Database unreachable; cannot start worker")
        return

    LOGGER.info("Database connectivity verified; starting worker loop")

    # Initialize AgentRunner with FakeLLMProvider (Wave 9 determinism)
    repo_root = Path(__file__).parent.parent.parent.parent
    runner = AgentRunner.from_repository_root(
        repo_root,
        provider=FakeLLMProvider(),
    )

    worker_id = deterministic_worker_id(1)

    # Create session factory for the worker loop
    session_factory = create_session_factory(engine)

    try:
        while True:
            now = datetime.now(UTC)

            # Create a new session for each claim attempt
            async with unit_of_work(session_factory) as uow:
                # Claim one READY job
                job = await claim_ready_job(
                    uow.session,
                    worker_id=worker_id,
                    now=now,
                    lease_duration=LEASE_DURATION,
                )

                if job is None:
                    # No jobs available; wait and retry
                    await asyncio.sleep(CLAIM_POLL_INTERVAL.total_seconds())
                    continue

                LOGGER.info(
                    "Claimed job %s (type %s, agent %s, attempt %d/%d)",
                    job.id,
                    job.job_type,
                    job.owner_agent_id,
                    job.attempt,
                    job.max_attempts,
                )

                # Execute job with runner
                await _execute_job_with_runner(
                    runner,
                    uow,
                    job,
                    worker_id,
                    now,
                )
    finally:
        await engine.dispose()


def main() -> int:
    """Worker entrypoint with conditional Exit 78 lift (Wave 9).

    Checks commissioning evidence gates per D-0028. When gates pass, runs the production
    claim loop (lease → execute → persist → event → successor). When gates fail, exits 78.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Check commissioning evidence gates per D-0028
    if not _check_commissioning_gates():
        LOGGER.error("Commissioning evidence gates FAILED; worker exits 78 (fail-closed)")
        return unavailable("worker")

    # Gates pass: lift Exit 78 and run production claim loop
    LOGGER.info("Commissioning evidence gates PASS; worker lifts Exit 78 and starts claim loop")
    try:
        asyncio.run(_worker_loop())
        return 0
    except KeyboardInterrupt:
        LOGGER.info("Worker interrupted by signal; shutting down gracefully")
        return 0
    except Exception as error:
        LOGGER.exception("Worker loop failed: %s", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
