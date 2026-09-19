"""Lease primitives concurrency tests.

Session 03 wave 2: deterministic tests proving lease exclusivity, heartbeat updates,
expiry handling, and graceful release. Uses throwaway databases and deterministic
worker IDs and job IDs (no random UUIDs).
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from money_machine.domain.enums import JobStatus
from money_machine.orchestration.leases import (
    LeaseExpiredError,
    LeaseNotHeldError,
    claim_ready_job,
    deterministic_worker_id,
    heartbeat,
    reclaim_expired_leases,
    release_lease,
)
from money_machine.persistence.tables import Job
from tests.integration.factories import NOW, make_job, make_shop, make_workflow


def deterministic_job_id(index: int) -> UUID:
    """Generate a deterministic UUID for job testing."""
    # Use the index to create a predictable UUID
    hex_str = f"{index:032x}"
    return UUID(hex_str)


async def test_single_worker_claims_ready_job(session: AsyncSession) -> None:
    """A worker claims a ready job and transitions it to RUNNING with lease fields."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    job = await make_job(session, workflow, status=JobStatus.READY.value, scheduled_at=NOW)

    worker_id = deterministic_worker_id(0)
    lease_duration = timedelta(minutes=5)

    claimed = await claim_ready_job(
        session,
        worker_id=worker_id,
        now=NOW,
        lease_duration=lease_duration,
    )

    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.status == JobStatus.RUNNING.value
    assert claimed.lease_owner == "worker-0"
    assert claimed.lease_expires_at == NOW + lease_duration
    assert claimed.heartbeat_at == NOW


async def test_claim_returns_none_when_no_ready_jobs(session: AsyncSession) -> None:
    """Claiming with no ready jobs returns None instead of raising."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    # Create PENDING job (not READY)
    await make_job(session, workflow, status=JobStatus.PENDING.value)

    worker_id = deterministic_worker_id(0)

    claimed = await claim_ready_job(
        session,
        worker_id=worker_id,
        now=NOW,
        lease_duration=timedelta(minutes=5),
    )

    assert claimed is None


async def test_two_workers_race_exactly_one_claims(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Two workers race to claim the same ready job; exactly one succeeds.

    This is the key concurrency test: FOR UPDATE SKIP LOCKED ensures mutual exclusion
    even under concurrent access. One worker gets the job, the other gets None.
    """
    # Setup: one ready job in a committed transaction
    async with session_factory() as setup_session:
        shop = await make_shop(setup_session)
        workflow = await make_workflow(setup_session, shop)
        job = await make_job(
            setup_session,
            workflow,
            status=JobStatus.READY.value,
            scheduled_at=NOW,
        )
        job_id = job.id
        await setup_session.commit()

    # Two workers with deterministic IDs
    worker_1_id = deterministic_worker_id(0)
    worker_2_id = deterministic_worker_id(1)
    lease_duration = timedelta(minutes=5)

    claims: list[Job | None] = []

    async def worker_claim(worker_id: str) -> None:
        """Each worker attempts to claim in its own session."""
        async with session_factory() as worker_session:
            claimed = await claim_ready_job(
                worker_session,
                worker_id=worker_id,
                now=NOW,
                lease_duration=lease_duration,
            )
            claims.append(claimed)
            await worker_session.commit()

    # Race both workers
    await asyncio.gather(
        worker_claim(worker_1_id),
        worker_claim(worker_2_id),
    )

    # Exactly one claim succeeded
    assert len([c for c in claims if c is not None]) == 1
    assert len([c for c in claims if c is None]) == 1

    # Verify the winner holds the lease
    winner_claim = next(c for c in claims if c is not None)
    assert winner_claim.id == job_id
    assert winner_claim.status == JobStatus.RUNNING.value
    assert winner_claim.lease_owner in {worker_1_id, worker_2_id}


async def test_heartbeat_updates_timestamp(session: AsyncSession) -> None:
    """Heartbeat updates the heartbeat_at timestamp without changing status."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    await make_job(session, workflow, status=JobStatus.READY.value)

    worker_id = deterministic_worker_id(0)

    # Claim the job
    claimed = await claim_ready_job(
        session,
        worker_id=worker_id,
        now=NOW,
        lease_duration=timedelta(minutes=5),
    )
    assert claimed is not None
    assert claimed.heartbeat_at == NOW

    # Heartbeat 30 seconds later
    later = NOW + timedelta(seconds=30)
    await heartbeat(session, job_id=claimed.id, worker_id=worker_id, now=later)

    # Refresh and verify
    await session.refresh(claimed)
    assert claimed.heartbeat_at == later
    assert claimed.status == JobStatus.RUNNING.value
    assert claimed.lease_owner == worker_id


async def test_heartbeat_rejects_wrong_worker(session: AsyncSession) -> None:
    """Heartbeat from a non-owner is rejected."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    await make_job(session, workflow, status=JobStatus.READY.value)

    owner = deterministic_worker_id(0)
    intruder = deterministic_worker_id(1)

    claimed = await claim_ready_job(
        session,
        worker_id=owner,
        now=NOW,
        lease_duration=timedelta(minutes=5),
    )
    assert claimed is not None

    with pytest.raises(LeaseNotHeldError, match="is owned by worker-0, not worker-1"):
        await heartbeat(session, job_id=claimed.id, worker_id=intruder, now=NOW)


async def test_heartbeat_rejects_expired_lease(session: AsyncSession) -> None:
    """Heartbeat after lease expiry is rejected."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    await make_job(session, workflow, status=JobStatus.READY.value)

    worker_id = deterministic_worker_id(0)
    lease_duration = timedelta(minutes=5)

    claimed = await claim_ready_job(
        session,
        worker_id=worker_id,
        now=NOW,
        lease_duration=lease_duration,
    )
    assert claimed is not None

    # Attempt heartbeat after expiry
    after_expiry = NOW + timedelta(minutes=6)

    with pytest.raises(LeaseExpiredError, match="expired at"):
        await heartbeat(session, job_id=claimed.id, worker_id=worker_id, now=after_expiry)


async def test_heartbeat_extends_lease(session: AsyncSession) -> None:
    """Heartbeat with lease_extension extends the lease_expires_at timestamp."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    await make_job(session, workflow, status=JobStatus.READY.value)

    worker_id = deterministic_worker_id(0)
    initial_lease = timedelta(minutes=5)

    # Claim the job
    claimed = await claim_ready_job(
        session,
        worker_id=worker_id,
        now=NOW,
        lease_duration=initial_lease,
    )
    assert claimed is not None
    original_expiry = NOW + initial_lease
    assert claimed.lease_expires_at == original_expiry

    # Heartbeat 2 minutes later with 5-minute extension
    later = NOW + timedelta(minutes=2)
    extension = timedelta(minutes=5)
    await heartbeat(
        session,
        job_id=claimed.id,
        worker_id=worker_id,
        now=later,
        lease_extension=extension,
    )

    # Refresh and verify lease was extended from 'later', not original claim time
    await session.refresh(claimed)
    assert claimed.heartbeat_at == later
    expected_new_expiry = later + extension  # 2 min + 5 min = 7 min from NOW
    assert claimed.lease_expires_at == expected_new_expiry
    assert claimed.status == JobStatus.RUNNING.value


async def test_release_lease_transitions_to_succeeded(session: AsyncSession) -> None:
    """Graceful release clears lease fields and transitions to final status."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    await make_job(session, workflow, status=JobStatus.READY.value)

    worker_id = deterministic_worker_id(0)

    claimed = await claim_ready_job(
        session,
        worker_id=worker_id,
        now=NOW,
        lease_duration=timedelta(minutes=5),
    )
    assert claimed is not None
    assert claimed.lease_owner == worker_id

    # Release with SUCCEEDED (legal from RUNNING)
    await release_lease(
        session,
        job_id=claimed.id,
        worker_id=worker_id,
        now=NOW + timedelta(seconds=10),
        final_status=JobStatus.SUCCEEDED,
    )

    await session.refresh(claimed)
    assert claimed.status == JobStatus.SUCCEEDED.value
    assert claimed.lease_owner is None
    assert claimed.lease_expires_at is None
    assert claimed.heartbeat_at is None


async def test_release_lease_rejects_wrong_worker(session: AsyncSession) -> None:
    """Release from a non-owner is rejected."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    await make_job(session, workflow, status=JobStatus.READY.value)

    owner = deterministic_worker_id(0)
    intruder = deterministic_worker_id(1)

    claimed = await claim_ready_job(
        session,
        worker_id=owner,
        now=NOW,
        lease_duration=timedelta(minutes=5),
    )
    assert claimed is not None

    with pytest.raises(LeaseNotHeldError, match="is owned by worker-0, not worker-1"):
        await release_lease(
            session,
            job_id=claimed.id,
            worker_id=intruder,
            now=NOW,
            final_status=JobStatus.SUCCEEDED,
        )


async def test_release_lease_rejects_illegal_status(session: AsyncSession) -> None:
    """Release to CANCELLED (illegal from RUNNING) is rejected."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    await make_job(session, workflow, status=JobStatus.READY.value)

    worker_id = deterministic_worker_id(0)

    claimed = await claim_ready_job(
        session,
        worker_id=worker_id,
        now=NOW,
        lease_duration=timedelta(minutes=5),
    )
    assert claimed is not None

    # CANCELLED is not legal from RUNNING
    with pytest.raises(ValueError, match="Cannot release to CANCELLED"):
        await release_lease(
            session,
            job_id=claimed.id,
            worker_id=worker_id,
            now=NOW,
            final_status=JobStatus.CANCELLED,
        )


async def test_reclaim_uses_legal_transition_path(session: AsyncSession) -> None:
    """Reclaim uses legal path: RUNNING → FAILED → READY and bumps attempt."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)
    await make_job(session, workflow, status=JobStatus.READY.value)

    worker_id = deterministic_worker_id(0)
    lease_duration = timedelta(minutes=5)

    # Worker claims the job
    claimed = await claim_ready_job(
        session,
        worker_id=worker_id,
        now=NOW,
        lease_duration=lease_duration,
    )
    assert claimed is not None
    assert claimed.status == JobStatus.RUNNING.value
    initial_attempt = claimed.attempt

    # Time passes, lease expires
    after_expiry = NOW + timedelta(minutes=6)

    reclaimed = await reclaim_expired_leases(session, now=after_expiry, limit=50)

    assert len(reclaimed) == 1
    assert reclaimed[0].id == claimed.id

    await session.refresh(claimed)
    # Final state is READY (via RUNNING → FAILED → READY)
    assert claimed.status == JobStatus.READY.value
    assert claimed.lease_owner is None
    assert claimed.lease_expires_at is None
    assert claimed.heartbeat_at is None
    # Lease expiry counts as a failed attempt, so attempt was bumped
    assert claimed.attempt == initial_attempt + 1


async def test_reclaim_respects_limit(session: AsyncSession) -> None:
    """Reclaim processes at most `limit` expired leases per call."""
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)

    worker_id = deterministic_worker_id(0)
    lease_duration = timedelta(minutes=5)

    # Create 5 expired jobs
    jobs: list[Job] = []
    for _ in range(5):
        await make_job(session, workflow, status=JobStatus.READY.value)
        claimed = await claim_ready_job(
            session,
            worker_id=worker_id,
            now=NOW,
            lease_duration=lease_duration,
        )
        assert claimed is not None
        jobs.append(claimed)

    after_expiry = NOW + timedelta(minutes=6)

    # Reclaim with limit=3
    reclaimed = await reclaim_expired_leases(session, now=after_expiry, limit=3)

    assert len(reclaimed) == 3

    # The remaining 2 can be reclaimed in the next call
    reclaimed_again = await reclaim_expired_leases(session, now=after_expiry, limit=10)
    assert len(reclaimed_again) == 2


async def test_worker_crash_and_reclaim_scenario(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Simulates worker crash: job is claimed, lease expires, second worker reclaims.

    This proves the full crash recovery flow:
    1. Worker 0 claims a job
    2. Worker 0 disappears (simulated by not releasing)
    3. Lease expires
    4. Lease reaper reclaims the job (RUNNING → FAILED → READY)
    5. Worker 1 claims and completes the job
    """
    # Setup
    async with session_factory() as setup_session:
        shop = await make_shop(setup_session)
        workflow = await make_workflow(setup_session, shop)
        job = await make_job(
            setup_session,
            workflow,
            status=JobStatus.READY.value,
            scheduled_at=NOW,
        )
        job_id = job.id
        await setup_session.commit()

    worker_0 = deterministic_worker_id(0)
    worker_1 = deterministic_worker_id(1)
    lease_duration = timedelta(minutes=5)

    # Worker 0 claims the job
    async with session_factory() as session_0:
        claimed = await claim_ready_job(
            session_0,
            worker_id=worker_0,
            now=NOW,
            lease_duration=lease_duration,
        )
        assert claimed is not None
        assert claimed.lease_owner == worker_0
        await session_0.commit()

    # Worker 0 crashes (we don't release)

    # Time passes, lease expires
    after_expiry = NOW + timedelta(minutes=6)

    # Lease reaper reclaims via legal path
    async with session_factory() as reaper_session:
        reclaimed = await reclaim_expired_leases(
            reaper_session,
            now=after_expiry,
            limit=50,
        )
        assert len(reclaimed) == 1
        assert reclaimed[0].id == job_id
        await reaper_session.commit()

    # Worker 1 claims the now-ready job
    async with session_factory() as session_1:
        claimed_by_1 = await claim_ready_job(
            session_1,
            worker_id=worker_1,
            now=after_expiry,
            lease_duration=lease_duration,
        )
        assert claimed_by_1 is not None
        assert claimed_by_1.id == job_id
        assert claimed_by_1.lease_owner == worker_1

        # Worker 1 completes the job
        await release_lease(
            session_1,
            job_id=job_id,
            worker_id=worker_1,
            now=after_expiry + timedelta(seconds=30),
            final_status=JobStatus.SUCCEEDED,
        )
        await session_1.commit()

    # Verify final state
    async with session_factory() as verify_session:
        from sqlalchemy import select

        statement = select(Job).where(Job.id == job_id)
        result = await verify_session.execute(statement)
        final_job = result.scalars().one()

        assert final_job.status == JobStatus.SUCCEEDED.value
        assert final_job.lease_owner is None


async def test_deterministic_worker_ids() -> None:
    """Worker ID generation is deterministic for reproducible tests."""
    assert deterministic_worker_id(0) == "worker-0"
    assert deterministic_worker_id(1) == "worker-1"
    assert deterministic_worker_id(99) == "worker-99"

    # Same index produces same ID
    assert deterministic_worker_id(0) == deterministic_worker_id(0)


async def test_reclaim_respects_retry_budget(session: AsyncSession) -> None:
    """When reclaim bumps attempt past max_attempts, job goes to TERMINAL_FAILURE.

    This is SHOULD-FIX #3: reclaim must respect retry budget, not READY forever.
    """
    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)

    # Create job with max_attempts=2, already at attempt 1
    await make_job(
        session,
        workflow,
        status=JobStatus.READY.value,
        scheduled_at=NOW,
        attempt=1,
        max_attempts=2,
    )

    # Claim the job
    worker_id = deterministic_worker_id(0)
    lease_duration = timedelta(minutes=5)
    claimed = await claim_ready_job(
        session, worker_id=worker_id, now=NOW, lease_duration=lease_duration
    )
    assert claimed is not None
    assert claimed.status == JobStatus.RUNNING.value

    # Lease expires
    after_expiry = NOW + timedelta(minutes=10)

    # Reclaim: RUNNING → FAILED (attempt 1 → 2) → check budget
    # Since attempt=2 >= max_attempts=2, should go to TERMINAL_FAILURE
    reclaimed = await reclaim_expired_leases(session, now=after_expiry, limit=50)

    assert len(reclaimed) == 1
    assert reclaimed[0].id == claimed.id
    assert reclaimed[0].status == JobStatus.TERMINAL_FAILURE.value
    assert reclaimed[0].attempt == 2
    assert reclaimed[0].lease_owner is None


async def test_reclaim_expired_lease_respects_retry_never(session: AsyncSession) -> None:
    """A-3 Blocker Fix: Jobs with RetryClass.NEVER move to TERMINAL_FAILURE on reclaim.

    When a job with retry_class=NEVER has its lease expire, reclaim_expired_leases
    must NOT transition it to READY. Instead, it should go RUNNING → FAILED → TERMINAL_FAILURE
    because NEVER means the failure is non-retryable.
    """
    from money_machine.domain.enums import RetryClass

    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)

    # Create job with RetryClass.NEVER, attempt=0, max_attempts=3
    # Even with budget remaining, NEVER should block retry
    job = Job(
        id=deterministic_job_id(100),
        workflow_id=workflow.id,
        job_type="TestJob",
        object_type="test",
        object_id=workflow.id,
        owner_agent_id="A99",
        status=JobStatus.READY.value,
        scheduled_at=NOW,
        attempt=0,
        max_attempts=3,
        idempotency_key="test_never_retry",
        side_effect_class="NONE",
        retry_class=RetryClass.NEVER.value,  # Non-retryable!
        allowed_mode="simulation",
        version=1,
    )
    session.add(job)
    await session.flush()

    # Worker claims the job
    worker_id = deterministic_worker_id(0)
    lease_duration = timedelta(minutes=5)
    claimed = await claim_ready_job(
        session, worker_id=worker_id, now=NOW, lease_duration=lease_duration
    )
    assert claimed is not None
    assert claimed.status == JobStatus.RUNNING.value
    assert claimed.attempt == 0

    # Lease expires
    after_expiry = NOW + timedelta(minutes=10)

    # Reclaim: RUNNING → FAILED (attempt 0 → 1) → TERMINAL_FAILURE (because NEVER)
    reclaimed = await reclaim_expired_leases(session, now=after_expiry, limit=50)

    assert len(reclaimed) == 1
    assert reclaimed[0].id == job.id
    assert reclaimed[0].status == JobStatus.TERMINAL_FAILURE.value, (
        "RetryClass.NEVER must move job to TERMINAL_FAILURE, not READY"
    )
    assert reclaimed[0].attempt == 1  # Bumped by lease expiry
    assert reclaimed[0].lease_owner is None


async def test_reclaim_expired_lease_respects_retry_manual_resume(session: AsyncSession) -> None:
    """A-3 Blocker Fix: Jobs with RetryClass.MANUAL_RESUME stay in FAILED on reclaim.

    When a job with retry_class=MANUAL_RESUME has its lease expire, reclaim_expired_leases
    must NOT transition it to READY. Instead, it should go RUNNING → FAILED and stay there,
    awaiting operator intervention.
    """
    from money_machine.domain.enums import RetryClass

    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)

    # Create job with RetryClass.MANUAL_RESUME, attempt=0, max_attempts=3
    # Even with budget remaining, MANUAL_RESUME should block automatic retry
    job = Job(
        id=deterministic_job_id(101),
        workflow_id=workflow.id,
        job_type="TestJob",
        object_type="test",
        object_id=workflow.id,
        owner_agent_id="A99",
        status=JobStatus.READY.value,
        scheduled_at=NOW,
        attempt=0,
        max_attempts=3,
        idempotency_key="test_manual_resume",
        side_effect_class="EXTERNAL_WRITE",
        retry_class=RetryClass.MANUAL_RESUME.value,  # Requires operator!
        allowed_mode="live",
        version=1,
    )
    session.add(job)
    await session.flush()

    # Worker claims the job
    worker_id = deterministic_worker_id(0)
    lease_duration = timedelta(minutes=5)
    claimed = await claim_ready_job(
        session, worker_id=worker_id, now=NOW, lease_duration=lease_duration
    )
    assert claimed is not None
    assert claimed.status == JobStatus.RUNNING.value
    assert claimed.attempt == 0

    # Lease expires
    after_expiry = NOW + timedelta(minutes=10)

    # Reclaim: RUNNING → FAILED (attempt 0 → 1), but do NOT transition to READY
    reclaimed = await reclaim_expired_leases(session, now=after_expiry, limit=50)

    assert len(reclaimed) == 1
    assert reclaimed[0].id == job.id
    assert reclaimed[0].status == JobStatus.FAILED.value, (
        "RetryClass.MANUAL_RESUME must stay in FAILED, not move to READY"
    )
    assert reclaimed[0].attempt == 1  # Bumped by lease expiry
    assert reclaimed[0].lease_owner is None


async def test_reclaim_expired_lease_allows_safe_retry(session: AsyncSession) -> None:
    """Verify that RetryClass.SAFE jobs DO transition to READY on reclaim (control test).

    This is the control test for A-3: jobs with SAFE, IDEMPOTENT, or RECONCILE_FIRST
    should still be allowed to retry normally (as long as budget remains).
    """
    from money_machine.domain.enums import RetryClass

    shop = await make_shop(session)
    workflow = await make_workflow(session, shop)

    # Create job with RetryClass.SAFE, attempt=0, max_attempts=3
    # This SHOULD transition to READY after reclaim (normal behavior)
    job = Job(
        id=deterministic_job_id(102),
        workflow_id=workflow.id,
        job_type="TestJob",
        object_type="test",
        object_id=workflow.id,
        owner_agent_id="A99",
        status=JobStatus.READY.value,
        scheduled_at=NOW,
        attempt=0,
        max_attempts=3,
        idempotency_key="test_safe_retry",
        side_effect_class="NONE",
        retry_class=RetryClass.SAFE.value,  # Safe to retry!
        allowed_mode="simulation",
        version=1,
    )
    session.add(job)
    await session.flush()

    # Worker claims the job
    worker_id = deterministic_worker_id(0)
    lease_duration = timedelta(minutes=5)
    claimed = await claim_ready_job(
        session, worker_id=worker_id, now=NOW, lease_duration=lease_duration
    )
    assert claimed is not None
    assert claimed.status == JobStatus.RUNNING.value
    assert claimed.attempt == 0

    # Lease expires
    after_expiry = NOW + timedelta(minutes=10)

    # Reclaim: RUNNING → FAILED (attempt 0 → 1) → READY (budget remains, SAFE allows retry)
    reclaimed = await reclaim_expired_leases(session, now=after_expiry, limit=50)

    assert len(reclaimed) == 1
    assert reclaimed[0].id == job.id
    assert reclaimed[0].status == JobStatus.READY.value, (
        "RetryClass.SAFE should allow transition to READY when budget remains"
    )
    assert reclaimed[0].attempt == 1  # Bumped by lease expiry
    assert reclaimed[0].lease_owner is None


async def test_reclaim_expired_leases_full_recovery_scenario(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """SF-1 Coverage: Full lease expiry recovery scenario.

    AUDIT.md SF-1 Acceptance:
    - Worker 1 claims job
    - Lease expires (time advance)
    - Worker 2 calls reclaim_expired_leases
    - Job transitions to READY
    - Worker 1 cannot heartbeat (LeaseExpiredError or LeaseNotHeldError)

    This proves that expired leases are identified, cleared, and the job becomes
    available for another worker.
    """
    # Setup: create a READY job in a committed transaction
    async with session_factory() as setup_session:
        shop = await make_shop(setup_session)
        workflow = await make_workflow(setup_session, shop)
        job = await make_job(
            setup_session,
            workflow,
            status=JobStatus.READY.value,
            scheduled_at=NOW,
            retry_class="SAFE",
        )
        job_id = job.id
        await setup_session.commit()

    worker_1 = deterministic_worker_id(0)
    worker_2 = deterministic_worker_id(1)
    lease_duration = timedelta(minutes=5)

    # Worker 1 claims the job
    async with session_factory() as session_1:
        claimed = await claim_ready_job(
            session_1,
            worker_id=worker_1,
            now=NOW,
            lease_duration=lease_duration,
        )
        assert claimed is not None
        assert claimed.id == job_id
        assert claimed.status == JobStatus.RUNNING.value
        assert claimed.lease_owner == worker_1
        await session_1.commit()

    # Time advances, lease expires
    after_expiry = NOW + timedelta(minutes=10)

    # Worker 2 calls reclaim_expired_leases
    async with session_factory() as reaper_session:
        reclaimed = await reclaim_expired_leases(
            reaper_session,
            now=after_expiry,
            limit=50,
        )
        assert len(reclaimed) == 1
        assert reclaimed[0].id == job_id
        assert reclaimed[0].status == JobStatus.READY.value, (
            "Job should transition back to READY after lease expiry (RetryClass.SAFE)"
        )
        assert reclaimed[0].lease_owner is None, "Lease should be cleared"
        await reaper_session.commit()

    # Worker 1 attempts heartbeat (should fail because lease expired)
    async with session_factory() as session_1_retry:
        with pytest.raises((LeaseExpiredError, LeaseNotHeldError)):
            await heartbeat(
                session_1_retry,
                job_id=job_id,
                worker_id=worker_1,
                now=after_expiry,
            )

    # Verify final state: job is READY and can be claimed by another worker
    async with session_factory() as verify_session:
        from sqlalchemy import select

        stmt = select(Job).where(Job.id == job_id)
        result = await verify_session.execute(stmt)
        final_job = result.scalars().one()

        assert final_job.status == JobStatus.READY.value
        assert final_job.lease_owner is None
        assert final_job.attempt == 1  # Bumped by lease expiry


async def test_heartbeat_raises_lease_expired_error(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """SF-4 Coverage: Heartbeat raises LeaseExpiredError when lease_expires_at < now.

    AUDIT.md SF-4 Acceptance:
    - Worker claims job with a lease
    - Time advances past lease_expires_at
    - Worker attempts heartbeat
    - Raises LeaseExpiredError

    This proves the heartbeat function correctly detects expired leases.
    """
    # Setup: create a READY job
    async with session_factory() as setup_session:
        shop = await make_shop(setup_session)
        workflow = await make_workflow(setup_session, shop)
        job = await make_job(
            setup_session,
            workflow,
            status=JobStatus.READY.value,
            scheduled_at=NOW,
        )
        job_id = job.id
        await setup_session.commit()

    worker_id = deterministic_worker_id(0)
    lease_duration = timedelta(minutes=5)

    # Worker claims the job
    async with session_factory() as session:
        claimed = await claim_ready_job(
            session,
            worker_id=worker_id,
            now=NOW,
            lease_duration=lease_duration,
        )
        assert claimed is not None
        assert claimed.lease_expires_at == NOW + lease_duration
        await session.commit()

    # Time advances past lease expiry
    after_expiry = NOW + timedelta(minutes=10)

    # Worker attempts heartbeat after lease expired
    async with session_factory() as session:
        with pytest.raises(LeaseExpiredError, match=r"Lease expired"):
            await heartbeat(
                session,
                job_id=job_id,
                worker_id=worker_id,
                now=after_expiry,
            )


async def test_heartbeat_raises_lease_not_held_error(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """SF-4 Coverage: Heartbeat raises LeaseNotHeldError when worker_id mismatches.

    AUDIT.md SF-4 Acceptance:
    - Worker 1 claims job with a lease
    - Worker 2 (different worker_id) attempts heartbeat
    - Raises LeaseNotHeldError

    This proves workers cannot heartbeat jobs they don't own.
    """
    # Setup: create a READY job
    async with session_factory() as setup_session:
        shop = await make_shop(setup_session)
        workflow = await make_workflow(setup_session, shop)
        job = await make_job(
            setup_session,
            workflow,
            status=JobStatus.READY.value,
            scheduled_at=NOW,
        )
        job_id = job.id
        await setup_session.commit()

    worker_1 = deterministic_worker_id(0)
    worker_2 = deterministic_worker_id(1)
    lease_duration = timedelta(minutes=5)

    # Worker 1 claims the job
    async with session_factory() as session:
        claimed = await claim_ready_job(
            session,
            worker_id=worker_1,
            now=NOW,
            lease_duration=lease_duration,
        )
        assert claimed is not None
        assert claimed.lease_owner == worker_1
        await session.commit()

    # Worker 2 attempts to heartbeat Worker 1's job
    async with session_factory() as session:
        with pytest.raises(LeaseNotHeldError, match=r"Worker .* does not hold lease"):
            await heartbeat(
                session,
                job_id=job_id,
                worker_id=worker_2,  # Different worker
                now=NOW + timedelta(seconds=30),
            )
