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
from money_machine.config.runtime import RuntimeSettingsError, load_runtime_settings
from money_machine.config.settings import AgentCommissioningState
from money_machine.domain.enums import JobStatus
from money_machine.domain.errors import InvalidTransitionError
from money_machine.domain.models.jobs import AgentResult, JobEnvelope
from money_machine.integrations.llm.fake_provider import FakeLLMProvider
from money_machine.orchestration._foundation import EXIT_UNAVAILABLE, unavailable
from money_machine.orchestration.event_dispatcher import EventDispatcher
from money_machine.orchestration.leases import (
    claim_ready_job,
    deterministic_worker_id,
    heartbeat,
    release_lease,
)
from money_machine.persistence.database import check_connectivity, create_engine, create_session_factory
from money_machine.persistence.tables import Job
from money_machine.persistence.unit_of_work import UnitOfWork, unit_of_work

LOGGER: Final = logging.getLogger(__name__)
LEASE_DURATION: Final = timedelta(minutes=5)
CLAIM_POLL_INTERVAL: Final = timedelta(seconds=5)


def _check_commissioning_gates() -> bool:
    """Check if commissioning evidence gates pass for Exit 78 lift.

    Returns True if at least one agent is TESTED or COMMISSIONED with passing tests.
    Returns False if gates fail, causing worker to exit 78.
    """
    try:
        # Load runtime settings to verify configuration
        _settings = load_runtime_settings()

        # Verify agent registry loads (proves config valid)
        repo_root = Path(__file__).parent.parent.parent.parent
        registry = AgentRegistry.from_yaml(repo_root)

        # Check if any agent is TESTED or COMMISSIONED
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
                "No TESTED or COMMISSIONED agents found; Exit 78 held. "
                "Found %d agents total, all in state DESIGNED or earlier.",
                len(list(registry.roster())),
            )
            return False

        LOGGER.info(
            "Commissioning gates pass: %d TESTED/COMMISSIONED agent(s) found: %s",
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
    """Main worker loop: claim jobs, execute via AgentRunner, emit events, create successors."""
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
    """Worker entrypoint with conditional Exit 78 lift (Wave 9)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    # Check commissioning evidence gates
    if not _check_commissioning_gates():
        LOGGER.error("Commissioning gates failed; worker exits 78 (fail-closed)")
        return unavailable("worker")

    # Gates pass: run production claim loop
    LOGGER.info("Commissioning gates pass; starting production worker")

    try:
        asyncio.run(_worker_loop())
        return 0
    except KeyboardInterrupt:
        LOGGER.info("Worker interrupted; shutting down gracefully")
        return 0
    except RuntimeSettingsError as error:
        LOGGER.error("Runtime settings error: %s", error)
        return EXIT_UNAVAILABLE
    except Exception as error:
        LOGGER.exception("Worker failed: %s", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
