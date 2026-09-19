"""Unit tests for dependency resolution logic.

Tests the dependency_resolver module's evaluation and promotion functions with
deterministic fake data. No external dependencies.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from money_machine.domain.enums import JobStatus
from money_machine.orchestration.dependency_resolver import (
    check_dependencies_satisfied,
    check_idempotency_collision,
    check_workflow_active,
    evaluate_job_readiness,
    promote_pending_to_ready,
    propagate_dependency_failure,
    satisfy_dependency,
)
from money_machine.persistence.tables import IdempotencyRecord, Job, JobDependency, WorkflowRun


@pytest.mark.asyncio
async def test_check_dependencies_satisfied_no_dependencies(db_session):
    """Job with no dependencies is considered satisfied."""
    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=datetime.now(UTC),
    )
    db_session.add(workflow)

    job_id = uuid4()
    job = Job(
        id=job_id,
        workflow_id=workflow_id,
        job_type="test_job",
        status=JobStatus.PENDING.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.flush()

    satisfied = await check_dependencies_satisfied(db_session, job_id=job_id)
    assert satisfied is True


@pytest.mark.asyncio
async def test_check_dependencies_satisfied_with_satisfied_dep(db_session):
    """Job with satisfied dependency is considered satisfied."""
    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=datetime.now(UTC),
    )
    db_session.add(workflow)

    predecessor_id = uuid4()
    predecessor = Job(
        id=predecessor_id,
        workflow_id=workflow_id,
        job_type="predecessor",
        status=JobStatus.SUCCEEDED.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=1,
        max_attempts=3,
    )
    db_session.add(predecessor)

    job_id = uuid4()
    job = Job(
        id=job_id,
        workflow_id=workflow_id,
        job_type="dependent",
        status=JobStatus.PENDING.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    db_session.add(job)

    now = datetime.now(UTC)
    dep = JobDependency(
        job_id=job_id,
        depends_on_job_id=predecessor_id,
        satisfied_at=now,  # Already satisfied
    )
    db_session.add(dep)
    await db_session.flush()

    satisfied = await check_dependencies_satisfied(db_session, job_id=job_id)
    assert satisfied is True


@pytest.mark.asyncio
async def test_check_dependencies_satisfied_with_unsatisfied_dep(db_session):
    """Job with unsatisfied dependency is NOT satisfied."""
    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=datetime.now(UTC),
    )
    db_session.add(workflow)

    predecessor_id = uuid4()
    predecessor = Job(
        id=predecessor_id,
        workflow_id=workflow_id,
        job_type="predecessor",
        status=JobStatus.READY.value,  # Not succeeded yet
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    db_session.add(predecessor)

    job_id = uuid4()
    job = Job(
        id=job_id,
        workflow_id=workflow_id,
        job_type="dependent",
        status=JobStatus.PENDING.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    db_session.add(job)

    dep = JobDependency(
        job_id=job_id,
        depends_on_job_id=predecessor_id,
        satisfied_at=None,  # Not satisfied
    )
    db_session.add(dep)
    await db_session.flush()

    satisfied = await check_dependencies_satisfied(db_session, job_id=job_id)
    assert satisfied is False


@pytest.mark.asyncio
async def test_check_workflow_active(db_session):
    """Active workflow (completed_at NULL) returns True."""
    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=datetime.now(UTC),
        completed_at=None,  # Active
    )
    db_session.add(workflow)
    await db_session.flush()

    active = await check_workflow_active(db_session, workflow_id=workflow_id)
    assert active is True


@pytest.mark.asyncio
async def test_check_workflow_inactive(db_session):
    """Completed workflow returns False."""
    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=datetime.now(UTC),
        completed_at=datetime.now(UTC),  # Completed
    )
    db_session.add(workflow)
    await db_session.flush()

    active = await check_workflow_active(db_session, workflow_id=workflow_id)
    assert active is False


@pytest.mark.asyncio
async def test_check_idempotency_collision_no_collision(db_session):
    """No collision when key is free."""
    job_id = uuid4()
    key = "test_key"

    collision = await check_idempotency_collision(
        db_session,
        job_id=job_id,
        idempotency_key=key,
    )
    assert collision is False


@pytest.mark.asyncio
async def test_check_idempotency_collision_same_job(db_session):
    """No collision when key reserved by same job."""
    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=datetime.now(UTC),
    )
    db_session.add(workflow)

    job_id = uuid4()
    job = Job(
        id=job_id,
        workflow_id=workflow_id,
        job_type="test_job",
        status=JobStatus.PENDING.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="EXTERNAL_WRITE",
        retry_class="IDEMPOTENT",
        attempt=0,
        max_attempts=3,
        idempotency_key="test_key",
    )
    db_session.add(job)

    record = IdempotencyRecord(
        idempotency_key="test_key",
        job_id=job_id,
        operation="test_op",
        side_effect_class="EXTERNAL_WRITE",
    )
    db_session.add(record)
    await db_session.flush()

    collision = await check_idempotency_collision(
        db_session,
        job_id=job_id,
        idempotency_key="test_key",
    )
    assert collision is False


@pytest.mark.asyncio
async def test_check_idempotency_collision_different_job(db_session):
    """Collision when key reserved by different job."""
    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=datetime.now(UTC),
    )
    db_session.add(workflow)

    other_job_id = uuid4()
    other_job = Job(
        id=other_job_id,
        workflow_id=workflow_id,
        job_type="other_job",
        status=JobStatus.RUNNING.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="EXTERNAL_WRITE",
        retry_class="IDEMPOTENT",
        attempt=1,
        max_attempts=3,
        idempotency_key="test_key",
    )
    db_session.add(other_job)

    record = IdempotencyRecord(
        idempotency_key="test_key",
        job_id=other_job_id,
        operation="test_op",
        side_effect_class="EXTERNAL_WRITE",
    )
    db_session.add(record)

    job_id = uuid4()
    job = Job(
        id=job_id,
        workflow_id=workflow_id,
        job_type="new_job",
        status=JobStatus.PENDING.value,
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="EXTERNAL_WRITE",
        retry_class="IDEMPOTENT",
        attempt=0,
        max_attempts=3,
        idempotency_key="test_key",
    )
    db_session.add(job)
    await db_session.flush()

    collision = await check_idempotency_collision(
        db_session,
        job_id=job_id,
        idempotency_key="test_key",
    )
    assert collision is True


@pytest.mark.asyncio
async def test_evaluate_job_readiness_all_conditions_met(db_session):
    """Job is ready when all conditions are met."""
    now = datetime.now(UTC)
    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=now,
        completed_at=None,
    )
    db_session.add(workflow)

    job_id = uuid4()
    job = Job(
        id=job_id,
        workflow_id=workflow_id,
        job_type="test_job",
        status=JobStatus.PENDING.value,
        scheduled_at=now - timedelta(seconds=1),  # Past
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.flush()

    is_ready, reason = await evaluate_job_readiness(db_session, job_id=job_id, now=now)
    assert is_ready is True
    assert "satisfied" in reason.lower()


@pytest.mark.asyncio
async def test_evaluate_job_readiness_not_time_yet(db_session):
    """Job is NOT ready when scheduled_at is in the future."""
    now = datetime.now(UTC)
    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=now,
    )
    db_session.add(workflow)

    job_id = uuid4()
    job = Job(
        id=job_id,
        workflow_id=workflow_id,
        job_type="test_job",
        status=JobStatus.PENDING.value,
        scheduled_at=now + timedelta(hours=1),  # Future
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.flush()

    is_ready, reason = await evaluate_job_readiness(db_session, job_id=job_id, now=now)
    assert is_ready is False
    assert "scheduled" in reason.lower()


@pytest.mark.asyncio
async def test_promote_pending_to_ready_success(db_session):
    """Successful promotion transitions PENDING → READY."""
    now = datetime.now(UTC)
    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=now,
    )
    db_session.add(workflow)

    job_id = uuid4()
    job = Job(
        id=job_id,
        workflow_id=workflow_id,
        job_type="test_job",
        status=JobStatus.PENDING.value,
        scheduled_at=now,
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.flush()

    promoted = await promote_pending_to_ready(db_session, job_id=job_id, now=now)

    assert promoted.id == job_id
    assert JobStatus(promoted.status) == JobStatus.READY
    assert promoted.updated_at == now


@pytest.mark.asyncio
async def test_promote_pending_to_ready_workflow_inactive(db_session):
    """Promotion fails when workflow is completed."""
    now = datetime.now(UTC)
    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=now,
        completed_at=now,  # Completed
    )
    db_session.add(workflow)

    job_id = uuid4()
    job = Job(
        id=job_id,
        workflow_id=workflow_id,
        job_type="test_job",
        status=JobStatus.PENDING.value,
        scheduled_at=now,
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    db_session.add(job)
    await db_session.flush()

    with pytest.raises(WorkflowInactiveError):
        await promote_pending_to_ready(db_session, job_id=job_id, now=now)


@pytest.mark.asyncio
async def test_satisfy_dependency(db_session):
    """Satisfying a dependency sets satisfied_at."""
    now = datetime.now(UTC)
    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=now,
    )
    db_session.add(workflow)

    predecessor_id = uuid4()
    predecessor = Job(
        id=predecessor_id,
        workflow_id=workflow_id,
        job_type="predecessor",
        status=JobStatus.SUCCEEDED.value,
        scheduled_at=now,
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=1,
        max_attempts=3,
    )
    db_session.add(predecessor)

    dependent_id = uuid4()
    dependent = Job(
        id=dependent_id,
        workflow_id=workflow_id,
        job_type="dependent",
        status=JobStatus.PENDING.value,
        scheduled_at=now,
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    db_session.add(dependent)

    dep = JobDependency(
        job_id=dependent_id,
        depends_on_job_id=predecessor_id,
        satisfied_at=None,
    )
    db_session.add(dep)
    await db_session.flush()

    count = await satisfy_dependency(db_session, succeeded_job_id=predecessor_id, now=now)
    assert count == 1

    # Verify satisfied_at is set
    updated_dep = await db_session.get(JobDependency, dep.id)
    assert updated_dep.satisfied_at == now


@pytest.mark.asyncio
async def test_propagate_dependency_failure(db_session):
    """Terminal failure blocks dependent PENDING jobs."""
    now = datetime.now(UTC)
    workflow_id = uuid4()
    workflow = WorkflowRun(
        id=workflow_id,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DESIGNED",
        started_at=now,
    )
    db_session.add(workflow)

    failed_id = uuid4()
    failed_job = Job(
        id=failed_id,
        workflow_id=workflow_id,
        job_type="failed",
        status=JobStatus.TERMINAL_FAILURE.value,
        scheduled_at=now,
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="NEVER",
        attempt=3,
        max_attempts=3,
    )
    db_session.add(failed_job)

    dependent_id = uuid4()
    dependent = Job(
        id=dependent_id,
        workflow_id=workflow_id,
        job_type="dependent",
        status=JobStatus.PENDING.value,
        scheduled_at=now,
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=0,
        max_attempts=3,
    )
    db_session.add(dependent)

    dep = JobDependency(
        job_id=dependent_id,
        depends_on_job_id=failed_id,
    )
    db_session.add(dep)
    await db_session.flush()

    blocked = await propagate_dependency_failure(
        db_session,
        failed_job_id=failed_id,
        now=now,
    )

    assert dependent_id in blocked
    updated = await db_session.get(Job, dependent_id)
    assert JobStatus(updated.status) == JobStatus.BLOCKED
