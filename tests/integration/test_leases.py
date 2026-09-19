"""Lease primitives concurrency tests.

Session 03 wave 2: deterministic tests proving lease exclusivity, heartbeat updates,
expiry handling, and graceful release. Uses throwaway databases and deterministic
worker IDs (no random UUIDs).
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

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

    # Release with SUCCEEDED
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


async def test_reclaim_expired_leases_resets_to_ready(session: AsyncSession) -> None:
    """Expired leases are reclaimed and reset to READY for another worker."""
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

    # Time passes, lease expires
    after_expiry = NOW + timedelta(minutes=6)

    reclaimed = await reclaim_expired_leases(session, now=after_expiry, limit=50)

    assert len(reclaimed) == 1
    assert reclaimed[0].id == claimed.id

    await session.refresh(claimed)
    assert claimed.status == JobStatus.READY.value
    assert claimed.lease_owner is None
    assert claimed.lease_expires_at is None
    assert claimed.heartbeat_at is None


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
    4. Lease reaper reclaims the job
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

    # Lease reaper reclaims
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
