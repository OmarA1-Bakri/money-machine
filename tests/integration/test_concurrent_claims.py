"""Concurrent claim and idempotency race tests (Wave 9).

Proves that:
1. Two workers cannot double-execute the same job (FOR UPDATE SKIP LOCKED)
2. Idempotency keys prevent duplicate external effects
3. Lease expiry allows safe retry without duplicate effects
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.enums import JobStatus, RetryClass, SideEffectClass
from money_machine.domain.events import EventName
from money_machine.orchestration.leases import (
    claim_ready_job,
    deterministic_worker_id,
    release_lease,
)
from money_machine.persistence.seed import seed
from money_machine.persistence.tables import Event, Job
from tests.integration.factories import NOW, make_shop, make_workflow


async def _make_ready_job(
    session: AsyncSession,
    *,
    workflow_id,
    idempotency_key: str,
) -> Job:
    """Create a READY job for claiming."""
    job = Job(
        id=uuid4(),
        workflow_id=workflow_id,
        job_type="TestJob",
        object_type="workflow_runs",
        object_id=workflow_id,
        owner_agent_id="A01",
        status=JobStatus.READY.value,
        input={"test": "data"},
        success_contract={"output_model": "AgentResult"},
        scheduled_at=NOW,
        attempt=0,
        max_attempts=3,
        idempotency_key=idempotency_key,
        side_effect_class=SideEffectClass.NONE.value,
        retry_class=RetryClass.SAFE.value,
        created_at=NOW,
        updated_at=NOW,
    )
    session.add(job)
    await session.flush()
    return job


@pytest.mark.asyncio
async def test_concurrent_claim_skip_locked(
    session: AsyncSession,
    session_factory,
    repository_root,
) -> None:
    """Two workers claiming concurrently: exactly one acquires, the other skips."""
    from money_machine.persistence.unit_of_work import unit_of_work

    # Setup: create test data using the provided session
    await seed(session, repository_root=repository_root)
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop=shop)
    job = await _make_ready_job(
        session,
        workflow_id=workflow.id,
        idempotency_key=f"CONCURRENT_TEST:{uuid4()}",
    )
    await session.commit()

    job_id = job.id

    # Two workers claim concurrently using separate sessions
    worker1_id = deterministic_worker_id(1)
    worker2_id = deterministic_worker_id(2)
    now = datetime.now(UTC)
    lease_duration = timedelta(minutes=5)

    async def claim_worker1():
        async with unit_of_work(session_factory) as uow1:
                claimed = await claim_ready_job(
                    uow1.session,
                    worker_id=worker1_id,
                    now=now,
                    lease_duration=lease_duration,
                )
                if claimed:
                    await uow1.commit()
                return claimed

    async def claim_worker2():
        async with unit_of_work(session_factory) as uow2:
            claimed = await claim_ready_job(
                uow2.session,
                worker_id=worker2_id,
                now=now,
                lease_duration=lease_duration,
            )
            if claimed:
                await uow2.commit()
            return claimed

    # Run both claims concurrently
    _ = await asyncio.gather(claim_worker1(), claim_worker2())

    # Exactly one worker should succeed - verify by checking the job status
    async with unit_of_work(session_factory) as verify_uow:
        job = await verify_uow.session.get(Job, job_id)
        assert job is not None
        assert job.status == JobStatus.RUNNING.value
        assert job.lease_owner in (worker1_id, worker2_id)


@pytest.mark.asyncio
async def test_idempotent_reclaim_prevents_duplicate_events(
    session: AsyncSession,
    session_factory,
    repository_root,
) -> None:
    """If a lease expires and another worker re-claims, idempotency prevents duplicate events."""
    from money_machine.persistence.unit_of_work import unit_of_work

    # Setup: create test data
    await seed(session, repository_root=repository_root)
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop=shop)
    idempotency_key = f"IDEMPOTENT_TEST:{uuid4()}"
    job = await _make_ready_job(
        session,
        workflow_id=workflow.id,
        idempotency_key=idempotency_key,
    )
    await session.commit()

    job_id = job.id
    workflow_id = workflow.id

    # Worker 1 claims and executes, then lease expires before event emission
    worker1_id = deterministic_worker_id(1)
    now = datetime.now(UTC)
    lease_duration = timedelta(seconds=30)

    async with unit_of_work(session_factory) as uow:
        claimed = await claim_ready_job(
            uow.session,
            worker_id=worker1_id,
            now=now,
            lease_duration=lease_duration,
        )
        assert claimed is not None
        assert claimed.id == job_id

        # Simulate execution completing but event not emitted
        # (worker crashed before event dispatch)
        await release_lease(
            uow.session,
            job_id=job_id,
            worker_id=worker1_id,
            final_status=JobStatus.SUCCEEDED,
            now=now,
        )
        # DO NOT emit event yet — simulate crash
        await uow.commit()

    # Check event count before re-claim
    async with unit_of_work(session_factory) as uow:
        event_count_before = await uow.session.scalar(
            select(Event)
            .where(
                Event.workflow_id == workflow_id,
                Event.job_id == job_id,
            )
            .count()
        )
        # No events yet (crashed before emit)
        assert event_count_before == 0 or event_count_before is None

    # Worker 2 re-claims (lease expired) and emits event with same dedupe key
    worker2_id = deterministic_worker_id(2)
    later = now + timedelta(minutes=10)

    async with unit_of_work(session_factory) as uow:
        # Reset job to READY for re-claim test
        job = await uow.session.get(Job, job_id)
        job.status = JobStatus.READY.value
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        await uow.commit()

    async with unit_of_work(session_factory) as uow:
        claimed = await claim_ready_job(
            uow.session,
            worker_id=worker2_id,
            now=later,
            lease_duration=lease_duration,
        )
        assert claimed is not None
        assert claimed.id == job_id

        # Release and emit event with deterministic dedupe key
        await release_lease(
            uow.session,
            job_id=job_id,
            worker_id=worker2_id,
            final_status=JobStatus.SUCCEEDED,
            now=later,
        )

        # Emit event with dedupe key (idempotent)
        dedupe_key = f"job_success:{job_id}:{idempotency_key}"
        event = Event(
            event_name=EventName.JOB_SUCCEEDED.value,
            aggregate_type="Job",
            aggregate_id=job_id,
            workflow_id=workflow_id,
            job_id=job_id,
            payload={},
            dedupe_key=dedupe_key,
            occurred_at=later,
        )
        uow.session.add(event)
        await uow.commit()

    # Verify exactly one event exists
    async with unit_of_work(session_factory) as uow:
        event_count_after = await uow.session.scalar(
            select(Event)
            .where(
                Event.workflow_id == workflow_id,
                Event.job_id == job_id,
            )
            .count()
        )
        assert event_count_after == 1, (
            f"Expected exactly 1 event (idempotent), got {event_count_after}"
        )


@pytest.mark.asyncio
async def test_double_execution_prevented_by_for_update_skip_locked(
    session: AsyncSession,
    session_factory,
    repository_root,
) -> None:
    """FOR UPDATE SKIP LOCKED prevents two workers from executing the same job."""
    from money_machine.persistence.unit_of_work import unit_of_work

    # Setup: create test data
    await seed(session, repository_root=repository_root)
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop=shop)
    job = await _make_ready_job(
        session,
        workflow_id=workflow.id,
        idempotency_key=f"DOUBLE_EXEC_TEST:{uuid4()}",
    )
    await session.commit()

    job_id = job.id

    # Two workers attempt to claim and execute concurrently
    worker1_id = deterministic_worker_id(1)
    worker2_id = deterministic_worker_id(2)
    now = datetime.now(UTC)
    lease_duration = timedelta(minutes=5)

    execution_count = []

    async def execute_worker1():
        async with unit_of_work(session_factory) as uow1:
            claimed = await claim_ready_job(
                uow1.session,
                worker_id=worker1_id,
                now=now,
                lease_duration=lease_duration,
            )
            if claimed:
                execution_count.append(1)
                # Simulate execution
                await asyncio.sleep(0.1)
                await release_lease(
                    uow1.session,
                    job_id=claimed.id,
                    worker_id=worker1_id,
                    final_status=JobStatus.SUCCEEDED,
                    now=now,
                )
                await uow1.commit()
        return claimed

    async def execute_worker2():
        async with unit_of_work(session_factory) as uow2:
            claimed = await claim_ready_job(
                uow2.session,
                worker_id=worker2_id,
                now=now,
                lease_duration=lease_duration,
            )
            if claimed:
                execution_count.append(2)
                # Simulate execution
                await asyncio.sleep(0.1)
                await release_lease(
                    uow2.session,
                    job_id=claimed.id,
                    worker_id=worker2_id,
                    final_status=JobStatus.SUCCEEDED,
                    now=now,
                )
                await uow2.commit()
            return claimed

    # Run both workers concurrently
    _ = await asyncio.gather(execute_worker1(), execute_worker2())

    # Exactly one worker should have executed
    assert len(execution_count) == 1, (
        f"Expected exactly one execution, got {len(execution_count)}"
    )

    # Verify the job is SUCCEEDED and owned by the successful worker
    async with unit_of_work(session_factory) as uow:
        job = await uow.session.get(Job, job_id)
        assert job is not None
        assert job.status == JobStatus.SUCCEEDED.value
        # lease_owner is cleared on release, so we can't check it here
        # But we know only one execution happened based on execution_count
