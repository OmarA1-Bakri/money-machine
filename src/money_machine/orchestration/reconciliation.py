"""Uncertain-effect reconciliation primitives using effect_attempts and idempotency_records.

Session 03 wave 3: library primitives with deterministic tests. Worker and scheduler remain
fail-closed (exit 78); commissioning is Session 04.

These helpers implement the reconciliation workflow from the Session 02 addendum (addendum
point 3): when a job reaches UNCERTAIN_EXTERNAL_EFFECT, reconcile by:
1. Reading idempotency_records to get the idempotency_key
2. Querying the latest effect_attempts row to get current reconciliation_attempt
3. Performing an EXTERNAL_READ of the provider to determine effect_state
4. Inserting a new effect_attempts row with updated state and incremented counter
5. Moving the job to SUCCEEDED (CONFIRMED), FAILED (ABSENT), or BLOCKED (UNKNOWN, budget exhausted)

Never mutate receipts (append-only). Never repeat the mutation. Reconciliation is always
an EXTERNAL_READ that queries provider state by idempotency_key.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Protocol

from money_machine.domain.enums import JobStatus
from money_machine.orchestration.idempotency import (
    get_idempotency_record,
    get_latest_effect_attempt,
    record_effect_attempt,
)
from money_machine.orchestration.transition_guard import require_job_transition
from money_machine.persistence.tables import Job

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession


class EffectState(StrEnum):
    """Reconciliation outcome for one attempted external effect (matches database taxonomy)."""

    CONFIRMED = "CONFIRMED"
    """The effect definitely happened; provider confirmed the object exists."""

    ABSENT = "ABSENT"
    """The effect definitely did not happen; provider has no record of it."""

    UNKNOWN = "UNKNOWN"
    """Cannot determine; provider query failed or returned ambiguous result."""


@dataclass(frozen=True, kw_only=True)
class ReconciliationResult:
    """The outcome of reconciling one uncertain external effect."""

    effect_state: EffectState
    """The determined state: CONFIRMED, ABSENT, or UNKNOWN."""

    next_job_status: JobStatus
    """The job status to transition to: SUCCEEDED, FAILED, or BLOCKED."""

    reconciliation_attempt: int
    """The reconciliation attempt number (0 = initial, increments per query)."""

    provider_object_id: str | None
    """Provider's ID for the object if CONFIRMED, None otherwise."""

    reason: str
    """Human-readable explanation of the reconciliation outcome."""


class ReconciliationBudgetExhausted(Exception):
    """Raised when a job has exhausted its reconciliation attempt budget."""


class ProviderReconciler(Protocol):
    """Protocol for provider-specific reconciliation implementations.

    A reconciler queries the provider to determine whether an uncertain external effect
    actually succeeded. This is always an EXTERNAL_READ that uses the idempotency_key
    to look up the object.

    Session 03 uses fake/stub implementations. Session 04 wires real provider adapters.
    """

    async def query_effect_state(
        self,
        *,
        idempotency_key: str,
        operation: str,
    ) -> tuple[EffectState, str | None]:
        """Query the provider to determine effect state.

        Args:
            idempotency_key: The effect's unique key
            operation: Operation name (e.g., "etsy.create_draft")

        Returns:
            (effect_state, provider_object_id):
            - (CONFIRMED, object_id) if the object exists
            - (ABSENT, None) if the provider has no record of it
            - (UNKNOWN, None) if the query failed or returned ambiguous result
        """
        ...


async def reconcile_uncertain_effect(
    session: AsyncSession,
    *,
    job_id: UUID,
    reconciler: ProviderReconciler,
    max_reconciliation_attempts: int = 3,
    now: datetime | None = None,
) -> ReconciliationResult:
    """Reconcile an uncertain external effect by querying the provider.

    This implements the Session 02 addendum's reconciliation workflow:
    1. Fetch the job and verify it's in UNCERTAIN_EXTERNAL_EFFECT
    2. Fetch the idempotency_records row
    3. Fetch the latest effect_attempts row to get current reconciliation count
    4. Call the provider reconciler to query effect state
    5. Insert a new effect_attempts row with the result
    6. Determine the next job status

    The job remains in UNCERTAIN_EXTERNAL_EFFECT until reconciliation succeeds or
    the reconciliation budget is exhausted (which moves it to BLOCKED).

    Args:
        session: Active database session
        job_id: The job to reconcile
        reconciler: Provider-specific reconciler implementation
        max_reconciliation_attempts: Maximum reconciliation queries (default 3)
        now: Current timestamp (defaults to datetime.now(UTC))

    Returns:
        ReconciliationResult with effect_state, next_job_status, and reason

    Raises:
        ValueError: If the job is not in UNCERTAIN_EXTERNAL_EFFECT
        ReconciliationBudgetExhausted: If reconciliation budget is exhausted
    """
    if now is None:
        now = datetime.now(UTC)

    # Fetch the job
    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError(f"job {job_id} not found")

    if job.status != JobStatus.UNCERTAIN_EXTERNAL_EFFECT.value:
        raise ValueError(
            f"job {job_id} is {job.status}, expected UNCERTAIN_EXTERNAL_EFFECT"
        )

    # Fetch the idempotency record
    idempotency_record = await get_idempotency_record(
        session, idempotency_key=job.idempotency_key
    )
    if idempotency_record is None:
        raise ValueError(
            f"no idempotency record for job {job_id} key {job.idempotency_key!r}"
        )

    # Fetch the latest effect attempt
    latest_attempt = await get_latest_effect_attempt(
        session, idempotency_key=job.idempotency_key
    )

    if latest_attempt is None:
        # No effect_attempts row exists yet; this is the first reconciliation
        current_reconciliation = 0
    else:
        current_reconciliation = latest_attempt.reconciliation_attempt

    # Check if budget is exhausted
    next_reconciliation = current_reconciliation + 1
    if next_reconciliation > max_reconciliation_attempts:
        raise ReconciliationBudgetExhausted(
            f"job {job_id} reconciliation budget exhausted "
            f"({next_reconciliation}/{max_reconciliation_attempts})"
        )

    # Query the provider to determine effect state
    effect_state, provider_object_id = await reconciler.query_effect_state(
        idempotency_key=job.idempotency_key,
        operation=idempotency_record.operation,
    )

    # Record the reconciliation attempt
    await record_effect_attempt(
        session,
        idempotency_key=job.idempotency_key,
        job_id=job_id,
        agent_run_id=None,  # Reconciliation is not an agent execution
        provider=_extract_provider(idempotency_record.operation),
        operation=idempotency_record.operation,
        effect_state=effect_state.value,
        provider_object_id=provider_object_id,
        reconciliation_attempt=next_reconciliation,
        now=now,
    )

    # Determine next job status based on effect state
    match effect_state:
        case EffectState.CONFIRMED:
            # Effect succeeded; move to SUCCEEDED
            next_status = JobStatus.SUCCEEDED
            reason = f"reconciled as CONFIRMED (attempt {next_reconciliation})"

        case EffectState.ABSENT:
            # Effect did not happen; move to FAILED so retry policy can evaluate
            next_status = JobStatus.FAILED
            reason = f"reconciled as ABSENT (attempt {next_reconciliation})"

        case EffectState.UNKNOWN:
            # Still uncertain; check if budget exhausted
            if next_reconciliation >= max_reconciliation_attempts:
                # Budget exhausted; move to BLOCKED and open an incident
                next_status = JobStatus.BLOCKED
                reason = (
                    f"reconciliation budget exhausted after {next_reconciliation} attempts"
                )
            else:
                # Budget remaining; stay in UNCERTAIN_EXTERNAL_EFFECT
                # (caller will retry reconciliation)
                next_status = JobStatus.UNCERTAIN_EXTERNAL_EFFECT
                reason = f"still UNKNOWN after {next_reconciliation} attempts"

    return ReconciliationResult(
        effect_state=effect_state,
        next_job_status=next_status,
        reconciliation_attempt=next_reconciliation,
        provider_object_id=provider_object_id,
        reason=reason,
    )


async def apply_reconciliation_result(
    session: AsyncSession,
    *,
    job_id: UUID,
    result: ReconciliationResult,
    now: datetime | None = None,
) -> None:
    """Apply a reconciliation result to a job, transitioning it to the determined status.

    This transitions the job from UNCERTAIN_EXTERNAL_EFFECT to:
    - SUCCEEDED (effect confirmed)
    - FAILED (effect absent, eligible for retry evaluation)
    - BLOCKED (reconciliation budget exhausted, requires operator intervention)

    Args:
        session: Active database session
        job_id: The job to update
        result: The reconciliation result
        now: Current timestamp (defaults to datetime.now(UTC))
    """
    if now is None:
        now = datetime.now(UTC)

    job = await session.get(Job, job_id)
    if job is None:
        raise ValueError(f"job {job_id} not found")

    current_status = JobStatus(job.status)

    # Validate the transition is legal
    require_job_transition(current_status, result.next_job_status)

    # Apply the transition
    job.status = result.next_job_status.value
    job.updated_at = now

    await session.flush()


def _extract_provider(operation: str) -> str:
    """Extract the provider name from an operation string.

    Operation format: {provider}.{action} (e.g., "etsy.create_draft", "notion.duplicate_page")

    Args:
        operation: The operation string

    Returns:
        The provider name
    """
    if "." in operation:
        return operation.split(".", 1)[0]
    return operation


class FakeReconciler:
    """Deterministic fake reconciler for testing.

    This stub always returns a configurable result without querying any real provider.
    Session 04 replaces this with real provider adapters.
    """

    def __init__(
        self,
        *,
        effect_state: EffectState = EffectState.CONFIRMED,
        provider_object_id: str | None = None,
    ) -> None:
        """Initialize the fake reconciler.

        Args:
            effect_state: The state to return (default CONFIRMED)
            provider_object_id: The object ID to return (default None)
        """
        self.effect_state = effect_state
        self.provider_object_id = provider_object_id

    async def query_effect_state(
        self,
        *,
        idempotency_key: str,
        operation: str,
    ) -> tuple[EffectState, str | None]:
        """Return the configured fake result."""
        return self.effect_state, self.provider_object_id
