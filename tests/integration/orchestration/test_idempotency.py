"""Integration tests for idempotency record reservation and effect tracking.

These tests use a real PostgreSQL database to verify the three-table effect-tracking
structure: idempotency_records, effect_attempts, and receipts (append-only).

All tests use deterministic UUIDs (no uuid4) for reproducibility.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from money_machine.domain.enums import JobStatus, RetryClass, SideEffectClass
from money_machine.orchestration.idempotency import (
    IdempotencyKeyReservedError,
    derive_idempotency_key,
    get_idempotency_record,
    get_latest_effect_attempt,
    mark_idempotency_completed,
    record_effect_attempt,
    record_receipt,
    reserve_idempotency_key,
)
from money_machine.persistence.tables import IdempotencyRecord, Job, Receipt, Shop, WorkflowRun

# Deterministic UUIDs for tests (no uuid4)
JOB_ID_1 = UUID("00000000-0000-0000-0000-000000000001")
JOB_ID_2 = UUID("00000000-0000-0000-0000-000000000002")
WORKFLOW_ID_1 = UUID("10000000-0000-0000-0000-000000000001")
SHOP_ID_1 = UUID("50000000-0000-0000-0000-000000000001")
OBJECT_ID_1 = UUID("20000000-0000-0000-0000-000000000001")
AGENT_RUN_ID_1 = UUID("30000000-0000-0000-0000-000000000001")


async def create_test_job(
    session: AsyncSession, job_id: UUID, status: JobStatus = JobStatus.PENDING
) -> Job:
    """Create a minimal test job for foreign key requirements."""
    now = datetime(2026, 9, 19, 1, 0, 0, tzinfo=UTC)

    # Check if shop already exists (to avoid duplicate key violations across tests)
    shop = await session.get(Shop, SHOP_ID_1)
    if not shop:
        shop = Shop(
            id=SHOP_ID_1,
            name="test-shop",
            connection_state="UNCONNECTED",
            timezone="UTC",
            active=True,
        )
        session.add(shop)
        await session.flush()

    # Check if workflow run already exists
    workflow_run = await session.get(WorkflowRun, WORKFLOW_ID_1)
    if not workflow_run:
        workflow_run = WorkflowRun(
            id=WORKFLOW_ID_1,
            shop_id=SHOP_ID_1,
            workflow_type="ProductLifecycleWorkflow",
            workflow_version=1,
            product_state="DISCOVERED",
            started_at=now,
        )
        session.add(workflow_run)
        await session.flush()

    # Now create the job with all required fields
    job = Job(
        id=job_id,
        workflow_id=WORKFLOW_ID_1,
        job_type="PublishListingJob",
        object_type="EtsyListing",
        object_id=OBJECT_ID_1,
        owner_agent_id="A01",
        status=status.value,
        input={},
        success_contract={},
        scheduled_at=now,
        attempt=0,
        max_attempts=3,
        idempotency_key=f"test-key-{job_id}",
        side_effect_class=SideEffectClass.EXTERNAL_WRITE.value,
        retry_class=RetryClass.SAFE.value,
        allowed_mode="simulation",
        created_at=now,
        updated_at=now,
    )
    session.add(job)
    await session.flush()
    return job


@pytest.mark.asyncio
async def test_reserve_idempotency_key_success(session: AsyncSession) -> None:
    """reserve_idempotency_key creates a row with the given key."""
    await create_test_job(session, JOB_ID_1)
    now = datetime(2026, 9, 19, 1, 0, 0, tzinfo=UTC)

    reservation = await reserve_idempotency_key(
        session,
        idempotency_key="test-key-1",
        job_id=JOB_ID_1,
        operation="etsy.create_draft",
        side_effect_class=SideEffectClass.EXTERNAL_WRITE,
        now=now,
    )

    assert reservation.idempotency_key == "test-key-1"
    assert reservation.job_id == JOB_ID_1
    assert reservation.reserved_at == now

    # Verify row exists in database
    statement = select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == "test-key-1")
    result = await session.execute(statement)
    record = result.scalars().one()

    assert record.idempotency_key == "test-key-1"
    assert record.job_id == JOB_ID_1
    assert record.operation == "etsy.create_draft"
    assert record.side_effect_class == SideEffectClass.EXTERNAL_WRITE.value
    assert record.reserved_at == now
    assert record.completed_at is None


@pytest.mark.asyncio
async def test_reserve_idempotency_key_raises_on_duplicate(session: AsyncSession) -> None:
    """reserve_idempotency_key raises IdempotencyKeyReservedError if key already exists."""
    await create_test_job(session, JOB_ID_1)
    await create_test_job(session, JOB_ID_2)
    now = datetime(2026, 9, 19, 1, 0, 0, tzinfo=UTC)

    # First reservation succeeds
    await reserve_idempotency_key(
        session,
        idempotency_key="test-key-1",
        job_id=JOB_ID_1,
        operation="etsy.create_draft",
        side_effect_class=SideEffectClass.EXTERNAL_WRITE,
        now=now,
    )

    # Second reservation fails
    with pytest.raises(IdempotencyKeyReservedError, match=r"test-key-1.*already reserved"):
        await reserve_idempotency_key(
            session,
            idempotency_key="test-key-1",
            job_id=JOB_ID_2,
            operation="etsy.create_draft",
            side_effect_class=SideEffectClass.EXTERNAL_WRITE,
            now=now,
        )


@pytest.mark.asyncio
async def test_mark_idempotency_completed(session: AsyncSession) -> None:
    """mark_idempotency_completed sets completed_at timestamp."""
    await create_test_job(session, JOB_ID_1)
    reserved_at = datetime(2026, 9, 19, 1, 0, 0, tzinfo=UTC)
    completed_at = datetime(2026, 9, 19, 1, 0, 5, tzinfo=UTC)

    # Reserve the key
    await reserve_idempotency_key(
        session,
        idempotency_key="test-key-1",
        job_id=JOB_ID_1,
        operation="etsy.create_draft",
        side_effect_class=SideEffectClass.EXTERNAL_WRITE,
        now=reserved_at,
    )

    # Mark as completed
    await mark_idempotency_completed(
        session,
        idempotency_key="test-key-1",
        now=completed_at,
    )

    # Verify completed_at is set
    record = await get_idempotency_record(session, idempotency_key="test-key-1")
    assert record is not None
    assert record.completed_at == completed_at


@pytest.mark.asyncio
async def test_get_idempotency_record_not_found(session: AsyncSession) -> None:
    """get_idempotency_record returns None if key doesn't exist."""
    record = await get_idempotency_record(session, idempotency_key="nonexistent")
    assert record is None


@pytest.mark.asyncio
async def test_record_effect_attempt_initial(session: AsyncSession) -> None:
    """record_effect_attempt creates initial effect_attempts row."""
    await create_test_job(session, JOB_ID_1)
    now = datetime(2026, 9, 19, 1, 0, 0, tzinfo=UTC)

    attempt = await record_effect_attempt(
        session,
        idempotency_key="test-key-1",
        job_id=JOB_ID_1,
        agent_run_id=AGENT_RUN_ID_1,
        provider="etsy",
        operation="etsy.create_draft",
        effect_state="CONFIRMED",
        provider_object_id="listing-123",
        reconciliation_attempt=0,
        now=now,
    )

    assert attempt.idempotency_key == "test-key-1"
    assert attempt.job_id == JOB_ID_1
    assert attempt.agent_run_id == AGENT_RUN_ID_1
    assert attempt.provider == "etsy"
    assert attempt.operation == "etsy.create_draft"
    assert attempt.effect_state == "CONFIRMED"
    assert attempt.provider_object_id == "listing-123"
    assert attempt.reconciliation_attempt == 0
    assert attempt.observed_at == now


@pytest.mark.asyncio
async def test_record_effect_attempt_reconciliation(session: AsyncSession) -> None:
    """record_effect_attempt increments reconciliation_attempt on subsequent calls."""
    await create_test_job(session, JOB_ID_1)
    now1 = datetime(2026, 9, 19, 1, 0, 0, tzinfo=UTC)
    now2 = datetime(2026, 9, 19, 1, 0, 5, tzinfo=UTC)

    # Initial attempt
    await record_effect_attempt(
        session,
        idempotency_key="test-key-1",
        job_id=JOB_ID_1,
        agent_run_id=AGENT_RUN_ID_1,
        provider="etsy",
        operation="etsy.create_draft",
        effect_state="UNKNOWN",
        provider_object_id=None,
        reconciliation_attempt=0,
        now=now1,
    )

    # Reconciliation attempt
    attempt2 = await record_effect_attempt(
        session,
        idempotency_key="test-key-1",
        job_id=JOB_ID_1,
        agent_run_id=None,  # Reconciliation is not an agent execution
        provider="etsy",
        operation="etsy.create_draft",
        effect_state="CONFIRMED",
        provider_object_id="listing-123",
        reconciliation_attempt=1,
        now=now2,
    )

    assert attempt2.reconciliation_attempt == 1
    assert attempt2.effect_state == "CONFIRMED"
    assert attempt2.provider_object_id == "listing-123"
    assert attempt2.agent_run_id is None


@pytest.mark.asyncio
async def test_get_latest_effect_attempt(session: AsyncSession) -> None:
    """get_latest_effect_attempt returns the row with highest reconciliation_attempt."""
    await create_test_job(session, JOB_ID_1)
    now1 = datetime(2026, 9, 19, 1, 0, 0, tzinfo=UTC)
    now2 = datetime(2026, 9, 19, 1, 0, 5, tzinfo=UTC)
    now3 = datetime(2026, 9, 19, 1, 0, 10, tzinfo=UTC)

    # Create three attempts
    await record_effect_attempt(
        session,
        idempotency_key="test-key-1",
        job_id=JOB_ID_1,
        agent_run_id=AGENT_RUN_ID_1,
        provider="etsy",
        operation="etsy.create_draft",
        effect_state="UNKNOWN",
        provider_object_id=None,
        reconciliation_attempt=0,
        now=now1,
    )

    await record_effect_attempt(
        session,
        idempotency_key="test-key-1",
        job_id=JOB_ID_1,
        agent_run_id=None,
        provider="etsy",
        operation="etsy.create_draft",
        effect_state="UNKNOWN",
        provider_object_id=None,
        reconciliation_attempt=1,
        now=now2,
    )

    await record_effect_attempt(
        session,
        idempotency_key="test-key-1",
        job_id=JOB_ID_1,
        agent_run_id=None,
        provider="etsy",
        operation="etsy.create_draft",
        effect_state="CONFIRMED",
        provider_object_id="listing-123",
        reconciliation_attempt=2,
        now=now3,
    )

    # get_latest_effect_attempt returns the one with reconciliation_attempt=2
    latest = await get_latest_effect_attempt(session, idempotency_key="test-key-1")
    assert latest is not None
    assert latest.reconciliation_attempt == 2
    assert latest.effect_state == "CONFIRMED"
    assert latest.observed_at == now3


@pytest.mark.asyncio
async def test_record_receipt_append_only(session: AsyncSession) -> None:
    """record_receipt creates append-only receipts; mutations are blocked.

    Receipts are immutable. Attempting to mutate a receipt should be rejected
    (either by database trigger or application constraint).
    """
    await create_test_job(session, JOB_ID_1)
    now = datetime(2026, 9, 19, 1, 0, 0, tzinfo=UTC)

    receipt = await record_receipt(
        session,
        job_id=JOB_ID_1,
        idempotency_key="test-key-1",
        provider="etsy",
        operation="etsy.create_draft",
        side_effect_class=SideEffectClass.EXTERNAL_WRITE,
        autonomy_mode="simulation",
        effect_state="CONFIRMED",
        provider_object_id="listing-123",
        amount=None,
        currency=None,
        safe_detail={"status": "draft"},
        now=now,
    )

    assert receipt.job_id == JOB_ID_1
    assert receipt.idempotency_key == "test-key-1"
    assert receipt.provider == "etsy"
    assert receipt.operation == "etsy.create_draft"
    assert receipt.effect_state == "CONFIRMED"
    assert receipt.provider_object_id == "listing-123"
    assert receipt.safe_detail == {"status": "draft"}

    # Verify row exists in database
    statement = select(Receipt).where(Receipt.idempotency_key == "test-key-1")
    result = await session.execute(statement)
    db_receipt = result.scalars().one()

    assert db_receipt.idempotency_key == "test-key-1"

    # Prove append-only: attempting to mutate the receipt should fail
    # (database trigger blocks UPDATE on receipts table)
    original_provider_object_id = db_receipt.provider_object_id
    db_receipt.provider_object_id = "mutated-id"

    from sqlalchemy.exc import DatabaseError

    with pytest.raises(DatabaseError):  # Database will reject UPDATE
        await session.flush()

    # Rollback the failed transaction
    await session.rollback()

    # Verify the receipt was NOT mutated
    result = await session.execute(statement)
    db_receipt = result.scalars().one()
    assert db_receipt.provider_object_id == original_provider_object_id


@pytest.mark.asyncio
async def test_record_receipt_with_amount(session: AsyncSession) -> None:
    """record_receipt handles EXTERNAL_SPEND with amount and currency."""
    await create_test_job(session, JOB_ID_1)
    now = datetime(2026, 9, 19, 1, 0, 0, tzinfo=UTC)

    receipt = await record_receipt(
        session,
        job_id=JOB_ID_1,
        idempotency_key="test-key-1",
        provider="etsy",
        operation="etsy.purchase_shipping",
        side_effect_class=SideEffectClass.EXTERNAL_SPEND,
        autonomy_mode="simulation",
        effect_state="CONFIRMED",
        provider_object_id="shipping-label-456",
        amount=Decimal("5.99"),
        currency="USD",
        safe_detail={"tracking": "1Z999"},
        now=now,
    )

    assert receipt.amount == Decimal("5.99")
    assert receipt.currency == "USD"
    assert receipt.side_effect_class == SideEffectClass.EXTERNAL_SPEND.value


@pytest.mark.asyncio
async def test_derive_idempotency_key_deterministic() -> None:
    """derive_idempotency_key produces deterministic keys."""
    key1 = derive_idempotency_key(
        job_type="PublishListingJob",
        workflow_id=WORKFLOW_ID_1,
        object_id=OBJECT_ID_1,
        operation="create_draft",
    )

    key2 = derive_idempotency_key(
        job_type="PublishListingJob",
        workflow_id=WORKFLOW_ID_1,
        object_id=OBJECT_ID_1,
        operation="create_draft",
    )

    assert key1 == key2
    assert "PublishListingJob" in key1
    assert "create_draft" in key1


@pytest.mark.asyncio
async def test_derive_idempotency_key_distinguishes_operations() -> None:
    """derive_idempotency_key creates different keys for different operations."""
    key_draft = derive_idempotency_key(
        job_type="PublishListingJob",
        workflow_id=WORKFLOW_ID_1,
        object_id=OBJECT_ID_1,
        operation="create_draft",
    )

    key_publish = derive_idempotency_key(
        job_type="PublishListingJob",
        workflow_id=WORKFLOW_ID_1,
        object_id=OBJECT_ID_1,
        operation="publish",
    )

    assert key_draft != key_publish
