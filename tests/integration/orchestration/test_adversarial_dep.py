"""Adversarial test for dependency resolution.

Tests that satisfied_at set but predecessor ≠ SUCCEEDED must NOT promote to READY.

All UUIDs are deterministic (no uuid4) for reproducibility.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.enums import JobStatus
from money_machine.orchestration.dependency_resolver import (
    check_dependencies_satisfied,
    evaluate_job_readiness,
)
from money_machine.persistence.tables import Job, JobDependency, Shop, WorkflowRun

# Deterministic UUIDs for reproducible tests
SHOP_ID = UUID("00000000-0000-0000-0000-000000000001")
WORKFLOW_ID = UUID("00000000-0000-0000-0000-000000000002")
PREDECESSOR_ID = UUID("00000000-0000-0000-0000-000000000003")
JOB_ID = UUID("00000000-0000-0000-0000-000000000004")


@pytest.mark.asyncio
async def test_adversarial_satisfied_at_set_but_predecessor_not_succeeded(session: AsyncSession):
    """Adversarial test: satisfied_at set but predecessor ≠ SUCCEEDED must NOT promote to READY.

    This tests the blocker-fix requirement: check_dependencies_satisfied must verify BOTH:
    1. satisfied_at IS NOT NULL (dependency marked satisfied)
    2. Predecessor job status = SUCCEEDED (actually succeeded)

    If satisfied_at is set but predecessor is FAILED/BLOCKED/etc, promotion must be rejected.
    """
    shop = Shop(
        id=SHOP_ID,
        name="test-shop",
        provider_shop_id="test-provider-id",
        connection_state="CONNECTED",
        timezone="UTC",
    )
    session.add(shop)

    workflow = WorkflowRun(
        id=WORKFLOW_ID,
        shop_id=SHOP_ID,
        workflow_type="test_workflow",
        workflow_version=1,
        product_state="DISCOVERED",
        started_at=datetime.now(UTC),
    )
    session.add(workflow)
    await session.flush()

    # Predecessor in FAILED status (not SUCCEEDED)
    predecessor = Job(
        idempotency_key=f"test_key_{PREDECESSOR_ID!s}",
        id=PREDECESSOR_ID,
        workflow_id=WORKFLOW_ID,
        job_type="predecessor",
        object_type="workflow_runs",
        object_id=WORKFLOW_ID,
        status=JobStatus.FAILED.value,  # NOT SUCCEEDED
        scheduled_at=datetime.now(UTC),
        owner_agent_id="A01",
        side_effect_class="NONE",
        retry_class="SAFE",
        attempt=1,
        max_attempts=3,
    )
    session.add(predecessor)

    job = Job(
        idempotency_key=f"test_key_{JOB_ID!s}",
        id=JOB_ID,
        workflow_id=WORKFLOW_ID,
        job_type="dependent",
        object_type="workflow_runs",
        object_id=WORKFLOW_ID,
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

    # ADVERSARIAL: satisfied_at is set (maliciously or by bug)
    # BUT predecessor status is FAILED, not SUCCEEDED
    dep = JobDependency(
        job_id=JOB_ID,
        depends_on_job_id=PREDECESSOR_ID,
        satisfied_at=now,  # Satisfied claimed!
    )
    session.add(dep)
    await session.flush()

    # check_dependencies_satisfied should return False
    # because predecessor is FAILED, not SUCCEEDED
    satisfied = await check_dependencies_satisfied(session, job_id=JOB_ID)
    assert satisfied is False, "Dependencies must NOT be satisfied when predecessor != SUCCEEDED"

    # Attempting to promote should fail
    is_ready, reason = await evaluate_job_readiness(session, job_id=JOB_ID, now=now)
    assert is_ready is False
    assert "dependencies" in reason.lower() or "not satisfied" in reason.lower()
