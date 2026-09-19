"""Unit tests for dependency resolution logic.

Tests the dependency_resolver module's evaluation and promotion functions with
deterministic fake data. No external dependencies.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.enums import JobStatus
from money_machine.orchestration.dependency_resolver import (
    WorkflowInactiveError,
    check_dependencies_satisfied,
    check_idempotency_collision,
    check_workflow_active,
    evaluate_job_readiness,
    promote_pending_to_ready,
    propagate_dependency_failure,
    satisfy_dependency,
)
from money_machine.persistence.tables import (
    IdempotencyRecord,
    Job,
    JobDependency,
    Shop,
    WorkflowRun,
)


@pytest.mark.asyncio
async def test_check_dependencies_satisfied_no_dependencies(session: AsyncSession):
    """Job with no dependencies is considered satisfied."""
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
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
        started_at=datetime.now(UTC),
    )
    session.add(workflow)

    job_id = uuid4()
    job = Job(
        idempotency_key=f"test_key_{str(job_id)}",
        id=job_id,
        workflow_id=workflow_id,
        job_type="test_job",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.PENDING.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    session.add(job)
    await session.flush()

    satisfied = await check_dependencies_satisfied(session, job_id=job_id)
    assert satisfied is True


@pytest.mark.asyncio
async def test_check_dependencies_satisfied_with_satisfied_dep(session: AsyncSession):
    """Job with satisfied dependency is considered satisfied."""
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
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
        started_at=datetime.now(UTC),
    )
    session.add(workflow)

    predecessor_id = uuid4()
    predecessor = Job(
        idempotency_key=f"test_key_{str(predecessor_id)}",
        id=predecessor_id,
        workflow_id=workflow_id,
        job_type="predecessor",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.SUCCEEDED.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=1,
        max_attempts=3,
    )
    session.add(predecessor)

    job_id = uuid4()
    job = Job(
        idempotency_key=f"test_key_{str(job_id)}",
        id=job_id,
        workflow_id=workflow_id,
        job_type="dependent",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.PENDING.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    session.add(job)

    now = datetime.now(UTC)
    dep = JobDependency(
        job_id=job_id,
        depends_on_job_id=predecessor_id,
        satisfied_at=now,  # Already satisfied
    )
    session.add(dep)
    await session.flush()

    satisfied = await check_dependencies_satisfied(session, job_id=job_id)
    assert satisfied is True


@pytest.mark.asyncio
async def test_check_dependencies_satisfied_with_unsatisfied_dep(session: AsyncSession):
    """Job with unsatisfied dependency is NOT satisfied."""
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
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
        started_at=datetime.now(UTC),
    )
    session.add(workflow)

    predecessor_id = uuid4()
    predecessor = Job(
        idempotency_key=f"test_key_{str(predecessor_id)}",
        id=predecessor_id,
        workflow_id=workflow_id,
        job_type="predecessor",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.READY.value,  # Not succeeded yet
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    session.add(predecessor)

    job_id = uuid4()
    job = Job(
        idempotency_key=f"test_key_{str(job_id)}",
        id=job_id,
        workflow_id=workflow_id,
        job_type="dependent",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.PENDING.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    session.add(job)

    dep = JobDependency(
        job_id=job_id,
        depends_on_job_id=predecessor_id,
        satisfied_at=None,  # Not satisfied
    )
    session.add(dep)
    await session.flush()

    satisfied = await check_dependencies_satisfied(session, job_id=job_id)
    assert satisfied is False


@pytest.mark.asyncio
async def test_check_workflow_active(session: AsyncSession):
    """Active workflow (completed_at NULL) returns True."""
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
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
        started_at=datetime.now(UTC),
        completed_at=None,  # Active
    )
    session.add(workflow)
    await session.flush()

    active = await check_workflow_active(session, workflow_id=workflow_id)
    assert active is True


@pytest.mark.asyncio
async def test_check_workflow_inactive(session: AsyncSession):
    """Completed workflow returns False."""
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
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
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),  # Completed
    )
    session.add(workflow)
    await session.flush()

    active = await check_workflow_active(session, workflow_id=workflow_id)
    assert active is False


@pytest.mark.asyncio
async def test_check_idempotency_collision_no_collision(session: AsyncSession):
    """No collision when key is free."""
    job_id = uuid4()
    key = "test_key"

    collision = await check_idempotency_collision(
        session,
        job_id=job_id,
        idempotency_key=key,
    )
    assert collision is False


@pytest.mark.asyncio
async def test_check_idempotency_collision_same_job(session: AsyncSession):
    """No collision when key reserved by same job."""
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
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
        started_at=datetime.now(UTC),
    )
    session.add(workflow)

    job_id = uuid4()
    job = Job(
        id=job_id,
        workflow_id=workflow_id,
        job_type="test_job",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.PENDING.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="EXTERNAL_WRITE",
        retry_class="IDEMPOTENT",
        attempt=0,
        max_attempts=3,
        idempotency_key="test_key",
    )
    session.add(job)

    record = IdempotencyRecord(
        idempotency_key="test_key",
        job_id=job_id,
        operation="test_op",
        side_effect_class="EXTERNAL_WRITE",
    )
    session.add(record)
    await session.flush()

    collision = await check_idempotency_collision(
        session,
        job_id=job_id,
        idempotency_key="test_key",
    )
    assert collision is False


@pytest.mark.asyncio
async def test_check_idempotency_collision_different_job(session: AsyncSession):
    """Collision when key reserved by different job."""
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
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
        started_at=datetime.now(UTC),
    )
    session.add(workflow)

    other_job_id = uuid4()
    other_job = Job(
        id=other_job_id,
        workflow_id=workflow_id,
        job_type="other_job",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.RUNNING.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="EXTERNAL_WRITE",
        retry_class="IDEMPOTENT",
        attempt=1,
        max_attempts=3,
        idempotency_key="test_key",
    )
    session.add(other_job)

    record = IdempotencyRecord(
        idempotency_key="test_key",
        job_id=other_job_id,
        operation="test_op",
        side_effect_class="EXTERNAL_WRITE",
    )
    session.add(record)

    job_id = uuid4()
    job = Job(
        id=job_id,
        workflow_id=workflow_id,
        job_type="new_job",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.PENDING.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="EXTERNAL_WRITE",
        retry_class="IDEMPOTENT",
        attempt=0,
        max_attempts=3,
        idempotency_key="test_key",
    )
    session.add(job)
    await session.flush()

    collision = await check_idempotency_collision(
        session,
        job_id=job_id,
        idempotency_key="test_key",
    )
    assert collision is True


@pytest.mark.asyncio
async def test_evaluate_job_readiness_all_conditions_met(session: AsyncSession):
    """Job is ready when all conditions are met."""
    now = datetime.now(UTC)
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
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
        completed_at=None,
    )
    session.add(workflow)

    job_id = uuid4()
    job = Job(
        idempotency_key=f"test_key_{str(job_id)}",
        id=job_id,
        workflow_id=workflow_id,
        job_type="test_job",
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
    session.add(job)
    await session.flush()

    is_ready, reason = await evaluate_job_readiness(session, job_id=job_id, now=now)
    assert is_ready is True
    assert "satisfied" in reason.lower()


@pytest.mark.asyncio
async def test_evaluate_job_readiness_not_time_yet(session: AsyncSession):
    """Job is NOT ready when scheduled_at is in the future."""
    now = datetime.now(UTC)
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
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

    job_id = uuid4()
    job = Job(
        idempotency_key=f"test_key_{str(job_id)}",
        id=job_id,
        workflow_id=workflow_id,
        job_type="test_job",
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
    session.add(job)
    await session.flush()

    is_ready, reason = await evaluate_job_readiness(session, job_id=job_id, now=now)
    assert is_ready is False
    assert "scheduled" in reason.lower()


@pytest.mark.asyncio
async def test_promote_pending_to_ready_success(session: AsyncSession):
    """Successful promotion transitions PENDING → READY."""
    now = datetime.now(UTC)
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
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

    job_id = uuid4()
    job = Job(
        idempotency_key=f"test_key_{str(job_id)}",
        id=job_id,
        workflow_id=workflow_id,
        job_type="test_job",
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
    session.add(job)
    await session.flush()

    promoted = await promote_pending_to_ready(session, job_id=job_id, now=now)

    assert promoted.id == job_id
    assert JobStatus(promoted.status) == JobStatus.READY
    assert promoted.updated_at == now


@pytest.mark.asyncio
async def test_promote_pending_to_ready_workflow_inactive(session: AsyncSession):
    """Promotion fails when workflow is completed."""
    now = datetime.now(UTC)
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
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

    job_id = uuid4()
    job = Job(
        idempotency_key=f"test_key_{str(job_id)}",
        id=job_id,
        workflow_id=workflow_id,
        job_type="test_job",
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
    session.add(job)
    await session.flush()

    with pytest.raises(WorkflowInactiveError):
        await promote_pending_to_ready(session, job_id=job_id, now=now)


@pytest.mark.asyncio
async def test_satisfy_dependency(session: AsyncSession):
    """Satisfying a dependency sets satisfied_at."""
    now = datetime.now(UTC)
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
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
        idempotency_key=f"test_key_{str(predecessor_id)}",
        id=predecessor_id,
        workflow_id=workflow_id,
        job_type="predecessor",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.SUCCEEDED.value,
        scheduled_at=now,
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=1,
        max_attempts=3,
    )
    session.add(predecessor)

    dependent_id = uuid4()
    dependent = Job(
        idempotency_key=f"test_key_{str(dependent_id)}",
        id=dependent_id,
        workflow_id=workflow_id,
        job_type="dependent",
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
    session.add(dependent)

    dep = JobDependency(
        job_id=dependent_id,
        depends_on_job_id=predecessor_id,
        satisfied_at=None,
    )
    session.add(dep)
    await session.flush()

    count = await satisfy_dependency(session, succeeded_job_id=predecessor_id, now=now)
    assert count == 1

    # Verify satisfied_at is set
    updated_dep = await session.get(JobDependency, dep.id)
    assert updated_dep is not None
    assert updated_dep.satisfied_at == now


@pytest.mark.asyncio
async def test_propagate_dependency_failure(session: AsyncSession):
    """Terminal failure blocks dependent PENDING jobs."""
    now = datetime.now(UTC)
    shop_id = uuid4()
    shop = Shop(
        id=shop_id,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
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

    failed_id = uuid4()
    failed_job = Job(
        idempotency_key=f"test_key_{str(failed_id)}",
        id=failed_id,
        workflow_id=workflow_id,
        job_type="failed",
        object_type="workflow_runs",
        object_id=workflow_id,
        status=JobStatus.TERMINAL_FAILURE.value,
        scheduled_at=now,
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="NEVER",
        attempt=3,
        max_attempts=3,
    )
    session.add(failed_job)

    dependent_id = uuid4()
    dependent = Job(
        idempotency_key=f"test_key_{str(dependent_id)}",
        id=dependent_id,
        workflow_id=workflow_id,
        job_type="dependent",
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
    session.add(dependent)

    dep = JobDependency(
        job_id=dependent_id,
        depends_on_job_id=failed_id,
    )
    session.add(dep)
    await session.flush()

    blocked = await propagate_dependency_failure(
        session,
        failed_job_id=failed_id,
        now=now,
    )

    assert dependent_id in blocked
    updated = await session.get(Job, dependent_id)
    assert updated is not None
    assert JobStatus(updated.status) == JobStatus.BLOCKED
