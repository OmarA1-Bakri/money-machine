"""Idempotency record reservation and external-effect deduplication primitives.

Session 03 wave 3: library primitives with deterministic tests. Worker and scheduler remain
fail-closed (exit 78); commissioning is Session 04.

These helpers implement the three-table effect-tracking structure from the Session 02 addendum:
- idempotency_records: reservation/deduplication (reserve before external write)
- effect_attempts: mutable reconciliation tracking (what actually happened)
- receipts: immutable committed ledger (append-only, never UPDATE)

The workflow is:
1. reserve_idempotency_key before any external write
2. If reservation succeeds, proceed with the external operation
3. After operation, create effect_attempt row with effect_state
4. Create receipt row in the same transaction as the job result
5. If uncertain, reconcile by querying effect_attempts and updating with new attempt
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from money_machine.domain.enums import SideEffectClass
from money_machine.persistence.tables import EffectAttempt, IdempotencyRecord, Receipt

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class IdempotencyKeyReservedError(Exception):
    """Raised when an idempotency key is already reserved."""


@dataclass(frozen=True, kw_only=True)
class IdempotencyReservation:
    """A successful idempotency key reservation."""

    record_id: UUID
    """The database ID of the idempotency_records row."""

    idempotency_key: str
    """The reserved key."""

    job_id: UUID
    """The job that reserved this key."""

    reserved_at: datetime
    """When the reservation was created."""


async def reserve_idempotency_key(
    session: AsyncSession,
    *,
    idempotency_key: str,
    job_id: UUID,
    operation: str,
    side_effect_class: SideEffectClass,
    now: datetime | None = None,
) -> IdempotencyReservation:
    """Reserve an idempotency key before an external write.

    This must be called before any external mutation. The unique constraint on
    idempotency_key ensures at-most-once execution: if the key is already reserved,
    this raises IdempotencyKeyReservedError and the caller must not proceed with the
    external operation.

    Args:
        session: Active database session
        idempotency_key: Unique key for this external effect
        job_id: The job performing the operation
        operation: Operation name (e.g., "etsy.create_draft", "notion.duplicate_page")
        side_effect_class: Effect classification (EXTERNAL_WRITE, EXTERNAL_SPEND, etc.)
        now: Current timestamp (defaults to datetime.now(UTC))

    Returns:
        IdempotencyReservation with the record ID and metadata

    Raises:
        IdempotencyKeyReservedError: If the key is already reserved
    """
    if now is None:
        now = datetime.now(UTC)

    record = IdempotencyRecord(
        idempotency_key=idempotency_key,
        job_id=job_id,
        operation=operation,
        side_effect_class=side_effect_class.value,
        reserved_at=now,
        completed_at=None,
    )

    session.add(record)

    try:
        await session.flush()
    except IntegrityError as exc:
        raise IdempotencyKeyReservedError(
            f"idempotency key {idempotency_key!r} already reserved"
        ) from exc

    return IdempotencyReservation(
        record_id=record.id,
        idempotency_key=idempotency_key,
        job_id=job_id,
        reserved_at=now,
    )


async def mark_idempotency_completed(
    session: AsyncSession,
    *,
    idempotency_key: str,
    now: datetime | None = None,
) -> None:
    """Mark an idempotency reservation as completed.

    Called after the external operation and receipt persistence succeed. This updates
    the completed_at timestamp on the idempotency_records row.

    Args:
        session: Active database session
        idempotency_key: The key to mark as completed
        now: Current timestamp (defaults to datetime.now(UTC))
    """
    if now is None:
        now = datetime.now(UTC)

    statement = select(IdempotencyRecord).where(
        IdempotencyRecord.idempotency_key == idempotency_key
    )

    result = await session.execute(statement)
    record = result.scalars().one_or_none()

    if record is None:
        raise ValueError(f"idempotency key {idempotency_key!r} not found")

    record.completed_at = now
    await session.flush()


async def get_idempotency_record(
    session: AsyncSession,
    *,
    idempotency_key: str,
) -> IdempotencyRecord | None:
    """Fetch an idempotency record by key.

    Args:
        session: Active database session
        idempotency_key: The key to look up

    Returns:
        The IdempotencyRecord row if found, None otherwise
    """
    statement = select(IdempotencyRecord).where(
        IdempotencyRecord.idempotency_key == idempotency_key
    )

    result = await session.execute(statement)
    return result.scalars().one_or_none()


async def get_latest_effect_attempt(
    session: AsyncSession,
    *,
    idempotency_key: str,
) -> EffectAttempt | None:
    """Fetch the latest effect_attempt row for a given idempotency key.

    Used by reconciliation to get the current reconciliation_attempt count and
    effect_state before querying the provider.

    Args:
        session: Active database session
        idempotency_key: The key to look up

    Returns:
        The latest EffectAttempt row (highest reconciliation_attempt), or None
    """
    statement = (
        select(EffectAttempt)
        .where(EffectAttempt.idempotency_key == idempotency_key)
        .order_by(EffectAttempt.reconciliation_attempt.desc())
        .limit(1)
    )

    result = await session.execute(statement)
    return result.scalars().first()


async def record_effect_attempt(
    session: AsyncSession,
    *,
    idempotency_key: str,
    job_id: UUID,
    agent_run_id: UUID | None,
    provider: str,
    operation: str,
    effect_state: str,
    provider_object_id: str | None,
    reconciliation_attempt: int,
    now: datetime | None = None,
) -> EffectAttempt:
    """Record one attempted external effect and its outcome.

    This is the mutable reconciliation-tracking table. A new row is inserted:
    - After the initial external write (reconciliation_attempt = 0)
    - After each reconciliation query (reconciliation_attempt increments)

    The latest row (highest reconciliation_attempt) is the current known state.

    Args:
        session: Active database session
        idempotency_key: The effect's unique key
        job_id: The job that attempted the operation
        agent_run_id: The agent run that performed it (None for reconciliation)
        provider: Provider name (e.g., "etsy", "notion")
        operation: Operation name (e.g., "create_draft", "duplicate_page")
        effect_state: CONFIRMED, ABSENT, or UNKNOWN
        provider_object_id: Provider's ID for the created object (None if ABSENT/UNKNOWN)
        reconciliation_attempt: 0 for initial attempt, increments for reconciliation
        now: Current timestamp (defaults to datetime.now(UTC))

    Returns:
        The created EffectAttempt row
    """
    if now is None:
        now = datetime.now(UTC)

    attempt = EffectAttempt(
        idempotency_key=idempotency_key,
        job_id=job_id,
        agent_run_id=agent_run_id,
        provider=provider,
        operation=operation,
        effect_state=effect_state,
        provider_object_id=provider_object_id,
        reconciliation_attempt=reconciliation_attempt,
        observed_at=now,
        recorded_at=now,
    )

    session.add(attempt)
    await session.flush()
    return attempt


async def record_receipt(
    session: AsyncSession,
    *,
    job_id: UUID,
    idempotency_key: str,
    provider: str,
    operation: str,
    side_effect_class: SideEffectClass,
    autonomy_mode: str,
    effect_state: str,
    provider_object_id: str | None,
    amount: Decimal | float | None = None,
    currency: str | None = None,
    safe_detail: dict[str, object] | None = None,
    now: datetime | None = None,
) -> Receipt:
    """Record an immutable committed effect in the append-only receipts table.

    This is the permanent ledger of what actually happened. Rows are never updated
    (enforced by database trigger). One receipt is created per successful external write
    in the same transaction as the job result.

    Args:
        session: Active database session
        job_id: The job that performed the operation
        idempotency_key: The effect's unique key
        provider: Provider name
        operation: Operation name
        side_effect_class: Effect classification
        autonomy_mode: simulation, draft, or live
        effect_state: CONFIRMED, ABSENT, or UNKNOWN
        provider_object_id: Provider's ID for the created object
        amount: Monetary amount if EXTERNAL_SPEND
        currency: Currency code if amount is set
        safe_detail: Redacted details (no credentials, no customer data)
        now: Current timestamp (defaults to datetime.now(UTC))

    Returns:
        The created Receipt row
    """
    if now is None:
        now = datetime.now(UTC)

    receipt = Receipt(
        job_id=job_id,
        idempotency_key=idempotency_key,
        provider=provider,
        operation=operation,
        side_effect_class=side_effect_class.value,
        autonomy_mode=autonomy_mode,
        effect_state=effect_state,
        provider_object_id=provider_object_id,
        amount=amount,
        currency=currency,
        safe_detail=safe_detail or {},
        recorded_at=now,
    )

    session.add(receipt)
    await session.flush()
    return receipt


def derive_idempotency_key(
    *,
    job_type: str,
    workflow_id: UUID,
    object_id: UUID,
    operation: str,
) -> str:
    """Derive a deterministic idempotency key for a job's external operation.

    The key format is: {job_type}:{workflow_id}:{object_id}:{operation}

    This ensures that:
    - The same job in the same workflow with the same object only executes once
    - Different operations on the same object get different keys
    - The key is reproducible and deterministic

    Args:
        job_type: The type of job (e.g., "PublishListingJob")
        workflow_id: The workflow UUID
        object_id: The object being operated on
        operation: The specific operation (e.g., "create_draft", "publish")

    Returns:
        A deterministic idempotency key
    """
    return f"{job_type}:{workflow_id}:{object_id}:{operation}"
