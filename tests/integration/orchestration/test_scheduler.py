"""Unit tests for scheduler functions.

Tests the scheduler module's promote, detect stalled, and timer functions with
deterministic fake data.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.enums import JobStatus
from money_machine.orchestration.scheduler import (
    DEFAULT_STALL_THRESHOLD,
    detect_stalled_jobs,
    promote_due_jobs,
    run_scheduler_cycle,
    schedule_maturity_timer,
)
from money_machine.persistence.tables import (
    Job,
    JobDependency,
    Shop,
    WorkflowRun,
)


@pytest.mark.asyncio
async def test_promote_due_jobs_success(session: AsyncSession):
    """Promote PENDING jobs that are due and have satisfied dependencies."""
    now = datetime.now(UTC)
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="ACTIVE",
        timezone="UTC",
    )
    session.add(shop)

    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        shop_id=shop_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=now,
    )
    session.add(workflow)

    # Job 1: due now, no dependencies
    job1_id = uuid4()
    job1 = Job(
        id=job1_id,
        workflow_id=workflow_id,
        job_type="job1",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.PENDING.value,
        scheduled_at=now - timedelta(seconds=1),  # Past
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    session.add(job1)

    # Job 2: due in future (should not promote)
    job2_id = uuid4()
    job2 = Job(
        id=job2_id,
        workflow_id=workflow_id,
        job_type="job2",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.PENDING.value,
        scheduled_at=now + timedelta(hours=1),  # Future
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    session.add(job2)

    await session.flush()

    promoted = await promote_due_jobs(session, now=now)

    assert len(promoted) == 1
    assert promoted[0].id == job1_id
    assert JobStatus(promoted[0].status) == JobStatus.READY


@pytest.mark.asyncio
async def test_promote_due_jobs_skips_unsatisfied_deps(session: AsyncSession):
    """Don't promote jobs with unsatisfied dependencies."""
    now = datetime.now(UTC)
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="ACTIVE",
        timezone="UTC",
    )
    session.add(shop)

    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        shop_id=shop_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=now,
    )
    session.add(workflow)

    predecessor_id = uuid4()
    predecessor = Job(
        id=predecessor_id,
        workflow_id=workflow_id,
        job_type="predecessor",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.READY.value,  # Not succeeded yet
        scheduled_at=now,
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    session.add(predecessor)

    dependent_id = uuid4()
    dependent = Job(
        id=dependent_id,
        workflow_id=workflow_id,
        job_type="dependent",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.PENDING.value,
        scheduled_at=now,  # Due now
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    session.add(dependent)

    dep = JobDependency(
        job_id=dependent_id,
        depends_on_job_id=predecessor_id,
        satisfied_at=None,  # Not satisfied
    )
    session.add(dep)
    await session.flush()

    promoted = await promote_due_jobs(session, now=now)

    assert len(promoted) == 0  # Nothing promoted


@pytest.mark.asyncio
async def test_detect_stalled_jobs(session: AsyncSession):
    """Detect RUNNING jobs that haven't heartbeated recently."""
    now = datetime.now(UTC)
    stale_heartbeat = now - DEFAULT_STALL_THRESHOLD - timedelta(minutes=1)

    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="ACTIVE",
        timezone="UTC",
    )
    session.add(shop)

    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        shop_id=shop_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=now - timedelta(hours=1),
    )
    session.add(workflow)

    # Stalled job: old heartbeat, lease not expired
    stalled_id = uuid4()
    stalled = Job(
        id=stalled_id,
        workflow_id=workflow_id,
        job_type="stalled",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.RUNNING.value,
        scheduled_at=now - timedelta(hours=1),
        lease_owner="worker-0",
        lease_expires_at=now + timedelta(minutes=10),  # Lease still valid
        heartbeat_at=stale_heartbeat,  # Old heartbeat
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=1,
        max_attempts=3,
    )
    session.add(stalled)

    # Not stalled: recent heartbeat
    active_id = uuid4()
    active = Job(
        id=active_id,
        workflow_id=workflow_id,
        job_type="active",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.RUNNING.value,
        scheduled_at=now - timedelta(hours=1),
        lease_owner="worker-1",
        lease_expires_at=now + timedelta(minutes=5),
        heartbeat_at=now - timedelta(seconds=30),  # Recent
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=1,
        max_attempts=3,
    )
    session.add(active)

    await session.flush()

    stalled_jobs = await detect_stalled_jobs(session, now=now)

    assert len(stalled_jobs) == 1
    assert stalled_jobs[0].id == stalled_id
    assert JobStatus(stalled_jobs[0].status) == JobStatus.FAILED
    assert stalled_jobs[0].attempt == 2  # Incremented


@pytest.mark.asyncio
async def test_detect_stalled_jobs_ignores_expired_lease(session: AsyncSession):
    """Expired leases are handled by reclaim_expired_leases, not stall detection."""
    now = datetime.now(UTC)
    stale_heartbeat = now - DEFAULT_STALL_THRESHOLD - timedelta(minutes=1)

    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="ACTIVE",
        timezone="UTC",
    )
    session.add(shop)

    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        shop_id=shop_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=now - timedelta(hours=1),
    )
    session.add(workflow)

    # Job with old heartbeat AND expired lease (not stalled, it's expired)
    expired_id = uuid4()
    expired = Job(
        id=expired_id,
        workflow_id=workflow_id,
        job_type="expired",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.RUNNING.value,
        scheduled_at=now - timedelta(hours=1),
        lease_owner="worker-0",
        lease_expires_at=now - timedelta(seconds=1),  # Expired
        heartbeat_at=stale_heartbeat,  # Old
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=1,
        max_attempts=3,
    )
    session.add(expired)

    await session.flush()

    stalled_jobs = await detect_stalled_jobs(session, now=now)

    # Should not detect this as stalled (it's expired)
    assert len(stalled_jobs) == 0


@pytest.mark.asyncio
async def test_schedule_maturity_timer(session: AsyncSession):
    """Schedule a maturity check timer for a workflow."""
    now = datetime.now(UTC)
    maturity_date = now + timedelta(days=30)

    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="ACTIVE",
        timezone="UTC",
    )
    session.add(shop)

    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        shop_id=shop_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=now,
    )
    session.add(workflow)
    await session.flush()

    timer_job = await schedule_maturity_timer(
        session,
        workflow_id=workflow_id,
        maturity_date=maturity_date,
        now=now,
    )

    assert timer_job is not None
    assert timer_job.job_type == "maturity_check"
    assert timer_job.scheduled_at == maturity_date
    assert JobStatus(timer_job.status) == JobStatus.PENDING


@pytest.mark.asyncio
async def test_schedule_maturity_timer_completed_workflow(session: AsyncSession):
    """Don't schedule timer for completed workflow."""
    now = datetime.now(UTC)
    maturity_date = now + timedelta(days=30)

    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="ACTIVE",
        timezone="UTC",
    )
    session.add(shop)

    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        shop_id=shop_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=now,
        completed_at=now,  # Completed
    )
    session.add(workflow)
    await session.flush()

    timer_job = await schedule_maturity_timer(
        session,
        workflow_id=workflow_id,
        maturity_date=maturity_date,
        now=now,
    )

    assert timer_job is None


@pytest.mark.asyncio
async def test_run_scheduler_cycle_integration(session: AsyncSession):
    """Run complete scheduler cycle."""
    now = datetime.now(UTC)

    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="ACTIVE",
        timezone="UTC",
    )
    session.add(shop)

    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        shop_id=shop_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=now,
    )
    session.add(workflow)

    # PENDING job due now (will be promoted)
    pending_id = uuid4()
    pending = Job(
        id=pending_id,
        workflow_id=workflow_id,
        job_type="pending",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.PENDING.value,
        scheduled_at=now,
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    session.add(pending)

    # RUNNING job with expired lease (will be reclaimed)
    expired_id = uuid4()
    expired = Job(
        id=expired_id,
        workflow_id=workflow_id,
        job_type="expired",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.RUNNING.value,
        scheduled_at=now - timedelta(hours=1),
        lease_owner="worker-0",
        lease_expires_at=now - timedelta(seconds=1),  # Expired
        heartbeat_at=now - timedelta(minutes=1),
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=1,
        max_attempts=3,
    )
    session.add(expired)

    # RUNNING job stalled (will be detected)
    stalled_id = uuid4()
    stalled = Job(
        id=stalled_id,
        workflow_id=workflow_id,
        job_type="stalled",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.RUNNING.value,
        scheduled_at=now - timedelta(hours=1),
        lease_owner="worker-1",
        lease_expires_at=now + timedelta(minutes=5),  # Not expired
        heartbeat_at=now - DEFAULT_STALL_THRESHOLD - timedelta(minutes=1),  # Stalled
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=1,
        max_attempts=3,
    )
    session.add(stalled)

    await session.flush()

    result = await run_scheduler_cycle(session, now=now)

    assert result["promoted"] == 1
    assert result["reclaimed"] == 1
    assert result["stalled"] == 1
