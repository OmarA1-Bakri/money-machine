"""One-product effects use the existing SQL reservations, attempts and receipts.

A committed reservation precedes the provider mutation. Replays only read and
reconcile; a missing result after an uncertain write never authorizes another POST.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from money_machine.application.real_draft_authority import DraftRunAuthority, DraftRunRefused
from money_machine.domain.enums import SideEffectClass
from money_machine.orchestration.idempotency import (
    derive_idempotency_key,
    get_idempotency_record,
    get_latest_effect_attempt,
    mark_idempotency_completed,
    record_effect_attempt,
    record_receipt,
    reserve_idempotency_key,
)
from money_machine.persistence.tables import Job, Shop, WorkflowRun

ProviderObject = Mapping[str, object]
Create = Callable[[], Awaitable[ProviderObject]]
Reconcile = Callable[[str | None], Awaitable[ProviderObject | None]]


class DraftEffectUncertain(RuntimeError):
    """Reservation retained; only authoritative reconciliation may resume it."""


class SqlDraftEffects:
    """A consumer of canonical orchestration tables, never a second engine."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        authority: DraftRunAuthority,
        job_id: UUID,
        *,
        lease_owner: str,
    ) -> None:
        self.factory = session_factory
        self.authority = authority
        self.job_id = job_id
        self.lease_owner = lease_owner
        self._active_key: ContextVar[str | None] = ContextVar("real_draft_effect_key", default=None)

    async def _scoped_job(self, session: AsyncSession) -> Job:
        """Lock static identity; accepted evidence remains recordable after cancellation."""
        job = await session.scalar(select(Job).where(Job.id == self.job_id).with_for_update())
        if (
            job is None
            or job.object_id != self.authority.product_id
            or job.input.get("run_id") != self.authority.run_id
            or job.allowed_mode != "draft"
            or job.side_effect_class != SideEffectClass.EXTERNAL_WRITE.value
        ):
            raise DraftRunRefused("durable_job_scope_or_lease")
        shop_name = await session.scalar(
            select(Shop.name)
            .join(WorkflowRun, WorkflowRun.shop_id == Shop.id)
            .where(WorkflowRun.id == job.workflow_id)
        )
        if shop_name != self.authority.shop_name:
            raise DraftRunRefused("durable_workflow_shop_scope")
        return job

    async def _job(self, session: AsyncSession) -> Job:
        job = await self._scoped_job(session)
        if (
            job.status != "RUNNING"
            or job.lease_owner != self.lease_owner
            or job.lease_expires_at is None
            or job.lease_expires_at <= datetime.now(UTC)
        ):
            raise DraftRunRefused("durable_job_scope_or_lease")
        return job

    async def assert_lease(self) -> None:
        """Adapter calls this after ancestry reads, immediately before its write."""
        key = self._active_key.get()
        if key is None:
            raise DraftRunRefused("active_effect_reservation_required")
        async with self.factory() as session, session.begin():
            await self._job(session)
            reservation = await get_idempotency_record(session, idempotency_key=key)
            if (
                reservation is None
                or reservation.job_id != self.job_id
                or reservation.completed_at is not None
            ):
                raise DraftRunRefused("active_effect_reservation_required")

    async def execute(
        self,
        operation_key: str,
        *,
        provider: str,
        operation: str,
        create: Create,
        reconcile: Reconcile,
        notion_parent_id: UUID | None = None,
        shop_id: int | None = None,
    ) -> ProviderObject:
        if provider not in {"notion", "etsy"} or not operation.startswith(provider + "."):
            raise DraftRunRefused("provider_scope")
        self.authority.authorize(
            operation,
            run_id=self.authority.run_id,
            product_id=self.authority.product_id,
            notion_parent_id=notion_parent_id,
            shop_name=self.authority.shop_name if provider == "etsy" else None,
            shop_id=shop_id,
        )
        async with self.factory() as session, session.begin():
            job = await self._job(session)
            key = derive_idempotency_key(
                job_type=job.job_type,
                workflow_id=job.workflow_id,
                object_id=job.object_id,
                operation=operation_key,
            )
            if len(key) > 200:
                raise DraftRunRefused("effect_key_too_long")
            existing = await get_idempotency_record(session, idempotency_key=key)
            fresh = existing is None
            if existing is not None and (
                existing.job_id != self.job_id or existing.operation != operation
            ):
                raise DraftRunRefused("reservation_scope")
            if fresh:
                await reserve_idempotency_key(
                    session,
                    idempotency_key=key,
                    job_id=self.job_id,
                    operation=operation,
                    side_effect_class=SideEffectClass.EXTERNAL_WRITE,
                )
            latest = await get_latest_effect_attempt(session, idempotency_key=key)
            known_id = latest.provider_object_id if latest else None
            may_create = fresh or bool(
                latest
                and latest.effect_state == "ABSENT"
                and existing
                and existing.completed_at is None
            )
            if may_create:
                # A durable in-flight claim prevents two ABSENT retries from writing.
                await record_effect_attempt(
                    session,
                    idempotency_key=key,
                    job_id=self.job_id,
                    agent_run_id=None,
                    provider=provider,
                    operation=operation,
                    effect_state="UNKNOWN",
                    provider_object_id=known_id,
                    reconciliation_attempt=latest.reconciliation_attempt + 1 if latest else 0,
                )
        # No database lock spans the provider request. Pending reservations are durable.
        mutation_started = False
        create_returned = False
        try:
            observed = await reconcile(known_id)
            if observed is None:
                if not may_create:
                    raise DraftEffectUncertain("pending_effect_not_yet_reconciled")
                # Reconciliation may outlive the lease or race a cancellation.
                # Re-check under the same canonical job lock before the effect.
                async with self.factory() as session, session.begin():
                    await self._job(session)
                    reservation = await get_idempotency_record(session, idempotency_key=key)
                    if reservation is None or reservation.completed_at is not None:
                        raise DraftEffectUncertain("effect_already_reconciled_before_write")
                mutation_started = True
                context = self._active_key.set(key)
                try:
                    created = await create()
                    create_returned = True
                finally:
                    self._active_key.reset(context)
                created_id = str(created.get("id", ""))
                if not created_id:
                    raise DraftEffectUncertain("provider_object_id_missing")
                # Preserve an accepted object's identity BEFORE any fallible QA/readback.
                known_id = created_id
                async with self.factory() as session, session.begin():
                    await self._scoped_job(session)
                    prior = await get_latest_effect_attempt(session, idempotency_key=key)
                    reservation = await get_idempotency_record(session, idempotency_key=key)
                    if (
                        reservation is None
                        or reservation.job_id != self.job_id
                        or reservation.operation != operation
                    ):
                        raise DraftEffectUncertain("accepted_effect_reservation_missing")
                    if reservation.completed_at is not None:
                        if (
                            prior is None
                            or prior.effect_state != "CONFIRMED"
                            or prior.provider_object_id != created_id
                        ):
                            raise DraftEffectUncertain("concurrent_confirmation_identity_mismatch")
                    else:
                        await record_effect_attempt(
                            session,
                            idempotency_key=key,
                            job_id=self.job_id,
                            agent_run_id=None,
                            provider=provider,
                            operation=operation,
                            effect_state="UNKNOWN",
                            provider_object_id=created_id,
                            reconciliation_attempt=prior.reconciliation_attempt + 1 if prior else 0,
                        )
                async with self.factory() as session, session.begin():
                    await self._job(session)
                observed = await reconcile(created_id)
                if observed is None or str(observed.get("id", "")) != created_id:
                    raise DraftEffectUncertain("fresh_provider_readback_missing")
            object_id = str(observed.get("id", ""))
            if not object_id or (known_id is not None and object_id != known_id):
                raise DraftEffectUncertain("provider_object_identity_mismatch")
        except Exception as exc:
            # Only trusted adapters may use DraftRunRefused for a definite refusal.
            # Timeouts, lost responses and uncertain writes never permit a new POST.
            definite_absence = may_create and (
                not mutation_started or (isinstance(exc, DraftRunRefused) and not create_returned)
            )
            async with self.factory() as session, session.begin():
                await self._job(session)
                prior = await get_latest_effect_attempt(session, idempotency_key=key)
                record = await get_idempotency_record(session, idempotency_key=key)
                if record is not None and record.completed_at is None:
                    await record_effect_attempt(
                        session,
                        idempotency_key=key,
                        job_id=self.job_id,
                        agent_run_id=None,
                        provider=provider,
                        operation=operation,
                        effect_state="ABSENT" if definite_absence else "UNKNOWN",
                        provider_object_id=None if definite_absence else known_id,
                        reconciliation_attempt=prior.reconciliation_attempt + 1 if prior else 0,
                    )
            if isinstance(exc, (DraftEffectUncertain, DraftRunRefused)):
                raise
            raise DraftEffectUncertain("provider_effect_requires_read_reconciliation") from None
        async with self.factory() as session, session.begin():
            await self._job(session)
            reservation = await get_idempotency_record(session, idempotency_key=key)
            if reservation is None:
                raise DraftRunRefused("reservation_missing")
            if reservation.completed_at is None:
                prior = await get_latest_effect_attempt(session, idempotency_key=key)
                await record_effect_attempt(
                    session,
                    idempotency_key=key,
                    job_id=self.job_id,
                    agent_run_id=None,
                    provider=provider,
                    operation=operation,
                    effect_state="CONFIRMED",
                    provider_object_id=object_id,
                    reconciliation_attempt=prior.reconciliation_attempt + 1 if prior else 0,
                )
                await record_receipt(
                    session,
                    job_id=self.job_id,
                    idempotency_key=key,
                    provider=provider,
                    operation=operation,
                    side_effect_class=SideEffectClass.EXTERNAL_WRITE,
                    autonomy_mode="draft",
                    effect_state="CONFIRMED",
                    provider_object_id=object_id,
                    safe_detail={
                        "run_id": self.authority.run_id,
                        "product_id": str(self.authority.product_id),
                        "provenance": "real_provider_readback",
                        "scope": "one_private_product_etsy_draft",
                    },
                )
                await mark_idempotency_completed(session, idempotency_key=key)
        return observed
