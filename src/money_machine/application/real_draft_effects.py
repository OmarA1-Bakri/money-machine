"""One-product effects use the existing SQL reservations, attempts and receipts.

A committed reservation precedes the provider mutation. Replays only read and
reconcile; a missing result after an uncertain write never authorizes another POST.
"""

from __future__ import annotations

from asyncio import current_task
from collections.abc import Awaitable, Callable, Mapping
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from money_machine.application.real_draft_authority import (
    DraftRunAuthority,
    DraftRunRefused,
    NotificationReplacementApproval,
    notion_request_sha256,
)
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
from money_machine.persistence.tables import AgentRun, Job, Shop, WorkflowRun

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
        agent_run_id: UUID | None = None,
    ) -> None:
        self.factory = session_factory
        self.authority = authority
        self.job_id = job_id
        self.lease_owner = lease_owner
        self.agent_run_id = agent_run_id
        self._recovery_permit: ContextVar[
            tuple[str, int, NotificationReplacementApproval] | None
        ] = ContextVar("recovery_wire_permit", default=None)
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
        if self.agent_run_id is not None:
            run = await session.get(AgentRun, self.agent_run_id)
            if run is None or run.job_id != job.id or run.agent_id != job.owner_agent_id:
                raise DraftRunRefused("durable_agent_run_scope")
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
        if self.agent_run_id is not None:
            run = await session.get(AgentRun, self.agent_run_id)
            if (
                run is None
                or run.status != "RUNNING"
                or run.completed_at is not None
                or run.job_attempt != job.attempt
                or run.lease_owner != self.lease_owner
            ):
                raise DraftRunRefused("active_agent_run_required")
        return job

    async def assert_lease(self) -> None:
        """Adapter calls this after ancestry reads, immediately before its write."""
        key = self._active_key.get()
        if key is None:
            raise DraftRunRefused("active_effect_reservation_required")
        async with self.factory() as session, session.begin():
            job = await self._job(session)
            permit = self._recovery_permit.get()
            if (
                "notification_recovery" in job.input
                or ":notification-replacement:" in key
                or permit is not None
            ):
                record = job.input.get("notification_recovery", {})
                if (
                    permit is None
                    or permit[:2] != (key, id(current_task()))
                    or not permit[2].approved_at <= datetime.now(UTC) < permit[2].expires_at
                    or not isinstance(record, dict)
                    or record.get("approval") != permit[2].model_dump(mode="json")
                    or record.get("effect_key") != key
                    or "send_consumed_at" not in record
                ):
                    raise DraftRunRefused("recovery_request_guard_required")
                self._recovery_permit.set(None)
            reservation = await get_idempotency_record(session, idempotency_key=key)
            if (
                reservation is None
                or reservation.job_id != self.job_id
                or reservation.completed_at is not None
            ):
                raise DraftRunRefused("active_effect_reservation_required")

    async def consume_notification_recovery_send(
        self,
        approval: NotificationReplacementApproval,
        method: str,
        path: str,
        body: dict[str, object],
    ) -> None:
        """Consume a persisted one-send grant at the adapter's actual request boundary.

        A consumed grant permits no further send, including after ABSENT or a
        crash before transport. Ordinary effects retain their existing policy.
        This never resolves the old UNKNOWN or closes a job/repair/incident.
        """
        if type(approval) is not NotificationReplacementApproval:
            raise DraftRunRefused("explicit_recovery_approval_required")
        now = datetime.now(UTC)
        if not approval.approved_at <= now < approval.expires_at:
            raise DraftRunRefused("recovery_approval_expired_or_future")
        if (
            method != "POST"
            or path != "databases"
            or set(body) != {"parent", "title", "is_inline", "initial_data_source"}
            or body.get("parent") != {"type": "page_id", "page_id": str(approval.parent_id)}
            or body.get("title") != [{"type": "text", "text": {"content": "Notification"}}]
            or body.get("is_inline") is not True
            or notion_request_sha256(body) != approval.request_sha256
        ):
            raise DraftRunRefused("recovery_request_digest_or_scope")
        key = self._active_key.get()
        async with self.factory() as session, session.begin():
            job = await self._job(session)
            expected_key = derive_idempotency_key(
                job_type=job.job_type,
                workflow_id=job.workflow_id,
                object_id=job.object_id,
                operation=approval.operation_key,
            )
            if (
                job.job_type != "BuildRepairJob"
                or job.owner_agent_id != "A07"
                or job.id != approval.repair_job_id
                or job.workflow_id != approval.workflow_id
                or job.object_id != approval.product_id
                or self.authority.run_id != approval.run_id
                or self.authority.verified_notion_parent_id != approval.parent_id
                or self.agent_run_id is None
                or key != expected_key
            ):
                raise DraftRunRefused("recovery_job_operation_scope")
            record = job.input.get("notification_recovery")
            if not isinstance(record, dict) or record.get("approval") != approval.model_dump(
                mode="json"
            ):
                raise DraftRunRefused("persisted_recovery_approval_required")
            if "send_consumed_at" in record:
                raise DraftRunRefused("recovery_send_authority_consumed")
            reservation = await get_idempotency_record(session, idempotency_key=expected_key)
            if (
                reservation is None
                or reservation.job_id != job.id
                or reservation.operation != "notion.private_product.write"
                or reservation.completed_at is not None
            ):
                raise DraftRunRefused("active_effect_reservation_required")
            original = await session.get(Job, approval.original_job_id)
            old_reservation = await get_idempotency_record(
                session, idempotency_key=approval.original_effect_key
            )
            old_attempt = await get_latest_effect_attempt(
                session, idempotency_key=approval.original_effect_key
            )
            if (
                original is None
                or original.id == job.id
                or original.workflow_id != job.workflow_id
                or original.object_id != job.object_id
                or original.input.get("run_id") != approval.run_id
                or (
                    original.status == "RUNNING"
                    and original.lease_expires_at is not None
                    and original.lease_expires_at > now
                )
                or old_reservation is None
                or old_reservation.job_id != original.id
                or old_reservation.completed_at is not None
                or old_attempt is None
                or old_attempt.id != approval.original_attempt_id
                or old_attempt.job_id != original.id
                or old_attempt.effect_state != "UNKNOWN"
                or old_attempt.provider != "notion"
                or old_attempt.operation != "notion.private_product.write"
            ):
                raise DraftRunRefused("original_unknown_scope_or_state")
            now = datetime.now(UTC)
            if not approval.approved_at <= now < approval.expires_at:
                raise DraftRunRefused("recovery_approval_expired_or_future")
            if job.lease_expires_at is None or job.lease_expires_at <= now:
                raise DraftRunRefused("durable_job_scope_or_lease")
            job.input = {
                **job.input,
                "notification_recovery": {
                    **record,
                    "send_consumed_at": now.isoformat(),
                    "effect_key": key,
                    "request_sha256": approval.request_sha256,
                    "agent_run_id": str(self.agent_run_id),
                },
            }
            await session.flush()
        # Only this task's next adapter lease guard can spend this in-memory permit.
        # Durable consumption above survives cancellation/process loss/DB readback failure.
        self._recovery_permit.set((expected_key, id(current_task()), approval))

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
                    agent_run_id=self.agent_run_id,
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
                    self._recovery_permit.set(None)
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
                            agent_run_id=self.agent_run_id,
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
                        agent_run_id=self.agent_run_id,
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
                    agent_run_id=self.agent_run_id,
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
                        **({"agent_run_id": str(self.agent_run_id)} if self.agent_run_id else {}),
                    },
                )
                await mark_idempotency_completed(session, idempotency_key=key)
        return observed
